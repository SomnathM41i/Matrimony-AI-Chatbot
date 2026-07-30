from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.chat_repository import ChatRepository
from app.services.llm_service import get_general_response
from app.services.db_query_service import answer_database_question_hybrid, DatabaseQueryError, accumulate_usage
from app.core.logger import logger, StepTimer
from datetime import datetime, timezone
import httpx
import json
import re
import uuid


def user_facing_error(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429:
        return (
            "Sorry, the assistant is receiving many requests right now. "
            "Please wait a moment and try again."
        )
    if isinstance(error, httpx.TimeoutException):
        return "Sorry, the request took too long to process. Please try again."
    if isinstance(error, DatabaseQueryError):
        return (
            "Sorry, I couldn't access the profile database right now. "
            "Please try again in a moment."
        )
    if isinstance(error, ValueError) and str(error) == "Could not convert request into a database query.":
        return (
            "Sorry, I couldn't understand that request in the current context. "
            "Please rephrase it—for example, 'Translate the previous answer into Marathi' "
            "or 'Show 5 female profiles from Pune.'"
        )
    return "Sorry, I couldn't process your request right now. Please try again or rephrase it."


def _word_in(text: str, word: str) -> bool:
    return bool(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text))

_DETAIL_CATEGORY_QUESTION = (
    "What would you like to know about this profile? I can tell you about:\n\n"
    "📚 **Education & Career** — education, occupation, income\n"
    "👨‍👩‍👧‍👦 **Family Details** — parents, siblings, family values\n"
    "🔮 **Horoscope & Manglik** — star, moon sign, manglik, gotra\n"
    "📍 **Location** — city, district, state\n"
    "🏋️ **Physical Attributes** — height, weight, blood group, complexion\n"
    "🌿 **Lifestyle** — diet, smoking, drinking, hobbies\n"
    "📷 **Photo & Contact** — photo, mobile number\n\n"
    "Just tell me which area you're interested in!"
)


def _is_profile_query(message: str, history: list[dict] | None = None) -> bool:
    msg = message.lower()
    profile_keywords = {
        "profile", "profiles", "member", "members", "bride", "groom",
        "girl", "girls", "boy", "boys", "woman", "women", "man", "men",
        "mulgi", "muli", "मुलगी", "मुली", "महिला",
        "mula", "mule", "मुलगा", "मुले", "पुरुष",
        "वधू", "वर", "प्रोफाइल", "सदस्य",
        "ladki", "ladkiyan", "लड़की", "लड़कियां",
        "unmarried", "divorced", "widow", "marital",
    }
    community_keywords = {
        "maratha", "brahmin", "mali", "kunbi", "dhangar",
        "hindu", "muslim", "buddhist", "jain", "christian", "sikh",
        "मराठा", "ब्राह्मण", "माळी", "हिंदू",
        "jat", "जात", "धर्म", "caste", "religion",
        "kuli", "कुळी",
    }
    has_profile_words = any(_word_in(msg, kw) for kw in profile_keywords)
    has_community_words = any(_word_in(msg, kw) for kw in community_keywords)
    has_search_verb = any(
        _word_in(msg, w) for w in [
            "show", "search", "find", "list", "दाखवा", "शोधा",
            "show me", "need", "want", "looking", "require",
            "हवी", "हवे", "पाहिजे",
        ]
    )
    return has_profile_words or has_community_words or has_search_verb


GREETING_RESPONSES: dict[str, str] = {
    "hi": "Hi! Welcome to myvivahai. How can I help you today?",
    "hello": "Hello! Welcome to myvivahai. How can I help you today?",
    "hey": "Hey there! Welcome to myvivahai. How can I help you today?",
    "नमस्कार": "नमस्कार! myvivahai मध्ये आपले स्वागत आहे. मी तुम्हाला कशी मदत करू?",
    "नमस्ते": "नमस्ते! myvivahai में आपका स्वागत है. मैं आपकी कैसे मदद कर सकता हूँ?",
    "हॅलो": "हॅलो! myvivahai मध्ये आपले स्वागत आहे. मी तुम्हाला कशी मदत करू?",
    "namaste": "Namaste! Welcome to myvivahai. How can I help you today?",
    "good morning": "Good morning! Welcome to myvivahai. How can I help you today?",
    "good afternoon": "Good afternoon! Welcome to myvivahai. How can I help you today?",
    "good evening": "Good evening! Welcome to myvivahai. How can I help you today?",
}


def _is_greeting_only(message: str) -> str | None:
    msg = message.lower().strip().rstrip(".!?,")
    for greeting, response in GREETING_RESPONSES.items():
        if msg == greeting:
            return response
    return None


def resolve_contextual_profile(
    selected_index: int | None,
    selected_reference: str | None,
    candidates: list[dict] | None,
    current_selected: dict | None
) -> tuple[dict | None, str | None]:
    if not candidates:
        return current_selected, None

    # 1. Resolve by index
    if selected_index is not None:
        try:
            idx = int(selected_index) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx], None
        except (ValueError, TypeError):
            pass

    # 2. Resolve by descriptive reference (Semantic reference resolution)
    if selected_reference:
        ref = str(selected_reference).lower().strip()
        matches = []
        for cand in candidates:
            match_found = False
            for key in ["Name", "Occupation", "Education", "City", "Maritalstatus", "Religion", "Caste"]:
                val = cand.get(key)
                if val and ref in str(val).lower():
                    match_found = True
                    break
            if match_found:
                matches.append(cand)

        # Confidence-based Decision Making
        if len(matches) == 1:
            # Exactly one matches -> HIGH confidence, proceed automatically!
            return matches[0], None
        elif len(matches) > 1:
            # Multiple matches -> LOW confidence, ask for clarification.
            names = ", ".join([f"'{c.get('Name')}'" for c in matches if c.get("Name")])
            clarification = f"I found multiple matches for '{selected_reference}': {names}. Which one did you mean?"
            return None, clarification

    return current_selected, None


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.msg_repo = ChatRepository(db)

    async def _load_history(self, conversation_id: int) -> tuple[list[dict], dict]:
        msgs = await self.msg_repo.list_by_conversation(conversation_id)
        history = []
        selected_profile = None
        accumulated_filters = None
        cached_profile_data = None
        profile_candidates = None
        for m in reversed(msgs):
            if not m.metadata_json:
                continue
            try:
                metadata = json.loads(m.metadata_json)
                if selected_profile is None:
                    selected_profile = metadata.get("selected_profile")
                if accumulated_filters is None:
                    accumulated_filters = metadata.get("accumulated_filters")
                if cached_profile_data is None:
                    cached_profile_data = metadata.get("cached_profile_data")
                if profile_candidates is None:
                    profile_candidates = metadata.get("profile_candidates")
            except (TypeError, ValueError):
                continue

        if selected_profile:
            history.append({
                "role": "system",
                "content": (
                "Persistent conversation state: the most recently resolved profile is "
                f"Name={selected_profile.get('Name', '')}, "
                f"MatriID={selected_profile.get('MatriID', '')}. "
                "Use this to resolve contextual references like 'her', 'she', 'this profile'."
                ),
            })

        for m in msgs[-settings.CHAT_HISTORY_LIMIT:]:
            history.append({"role": m.role, "content": m.content})
        return history, {
            "accumulated_filters": accumulated_filters,
            "selected_profile": selected_profile,
            "cached_profile_data": cached_profile_data,
            "profile_candidates": profile_candidates
        }

    async def stream_process_message(
        self, user_id: int, message: str, conversation_id: int | None = None
    ):
        greeting_reply = _is_greeting_only(message)
        if greeting_reply and not conversation_id:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)
            _ = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id,
                role="user", content=message,
            )
            assistant_msg = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id,
                role="assistant", content=greeting_reply,
            )
            await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            await self.db.commit()
            yield f"data: {json.dumps({'type': 'token', 'content': greeting_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv.id, 'message_id': assistant_msg.id, 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}})}\n\n"
            return

        request_id = uuid.uuid4().hex
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv or conv.user_id != user_id:
                raise ValueError("Conversation not found")
        else:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)

        history, conversation_context = await self._load_history(conv.id)

        user_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=message,
        )
        await self.db.commit()

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        events = []
        request_type = "normal"
        response_metadata = None
        reply_text = ""
        collected_tokens = []

        try:
            from app.services.extraction_service import extract_search_params
            from app.services.query_builder import build_profile_query
            from app.services.llm_service import stream_general_response, stream_format_db_result, format_db_notice
            from app.services.db_query_service import execute_param_query

            timer = StepTimer()
            timer.begin("analyze")
            yield f"data: {json.dumps({'type': 'status', 'step': 'analyze'})}\n\n"

            extracted = await extract_search_params(message, history=history, db=self.db)
            intent = extracted.get("intent", "general")

            if intent in ("profile_search", "profile_detail"):
                request_type = "database"
                ctx = conversation_context or {}
                accumulated_filters = ctx.get("accumulated_filters")
                selected_profile = ctx.get("selected_profile")
                candidates = ctx.get("profile_candidates")

                if intent == "profile_detail":
                    selected_index = extracted.get("selected_index")
                    selected_reference = extracted.get("selected_reference")

                    resolved, clarification = resolve_contextual_profile(
                        selected_index, selected_reference, candidates, selected_profile
                    )
                    if clarification:
                        reply_text = clarification
                        yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                        response_metadata = {
                            "selected_profile": selected_profile,
                            "accumulated_filters": accumulated_filters,
                            "profile_candidates": candidates,
                        }
                    else:
                        selected_profile = resolved
                        matri_id = selected_profile.get("MatriID") if selected_profile else None
                        name = selected_profile.get("Name") if selected_profile else None
                        if not matri_id and not name:
                            reply_text = "Which profile would you like details about? Please select one first."
                            yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                            response_metadata = {"selected_profile": None, "accumulated_filters": {}, "profile_candidates": candidates}
                        elif extracted.get("fields") in (None, ["all"]):
                            reply_text = _DETAIL_CATEGORY_QUESTION
                            yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                            response_metadata = {"selected_profile": selected_profile, "accumulated_filters": accumulated_filters, "profile_candidates": candidates}
                        if not reply_text:
                            cached = ctx.get("cached_profile_data")
                            if cached and str(cached.get("MatriID")) == str(matri_id):
                                sql_result = {"sql": "cached", "rows": [cached], "row_count": 1}
                                from app.services.db_query_service import _add_photo_url
                                for row in sql_result["rows"]:
                                    _add_photo_url(row)
                            else:
                                from app.services.query_builder import build_detail_query
                                fields = extracted.get("fields")
                                timer.begin("search")
                                yield f"data: {json.dumps({'type': 'status', 'step': 'search'})}\n\n"
                                sql, params = build_detail_query(matri_id=matri_id, name=name, fields=fields, limit=extracted.get("limit", 1))
                                sql_result = await execute_param_query(sql, params)
                                if sql_result.get("rows"):
                                    from app.services.db_query_service import _add_photo_url
                                    for row in sql_result["rows"]:
                                        _add_photo_url(row)
                            if not sql_result.get("rows"):
                                reply_text = "Profile not found."
                                yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                            else:
                                from app.services.db_query_service import _message_asks_about_unavailable_attribute
                                if _message_asks_about_unavailable_attribute(message):
                                    notice = await format_db_notice(message, "This information is not available in the database.", history=history, db=self.db)
                                    reply_text = notice.get("content", "This information is not available in the database.")
                                    yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                                else:
                                    timer.begin("format")
                                    yield f"data: {json.dumps({'type': 'status', 'step': 'format'})}\n\n"
                                    async for token, final in stream_format_db_result(message, sql_result, history=history, db=self.db):
                                        if token:
                                            collected_tokens.append(token)
                                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                                        if final:
                                            usage = accumulate_usage(usage, final.get("usage", {}))
                                            events.extend(final.get("events", []))
                                            reply_text = final.get("content", "".join(collected_tokens))
                                profile_rows = [{"MatriID": r.get("MatriID"), "Name": r.get("Name")} for r in sql_result["rows"] if r.get("Name")]
                                response_metadata = {
                                    "selected_profile": selected_profile if selected_profile else (profile_rows[0] if profile_rows else None),
                                    "accumulated_filters": {},
                                    "cached_profile_data": sql_result["rows"][0] if sql_result.get("rows") else None,
                                    "profile_candidates": candidates if candidates else (profile_rows if profile_rows else None),
                                }
                else:
                    new_filters = extracted.get("filters", {})
                    from app.services.db_query_service import _merge_filters
                    filters = _merge_filters(accumulated_filters, new_filters)
                    limit = extracted.get("limit", 10)
                    timer.begin("search")
                    yield f"data: {json.dumps({'type': 'status', 'step': 'search'})}\n\n"
                    sql, params = build_profile_query(filters, limit=limit)
                    sql_result = await execute_param_query(sql, params)
                    profile_rows = [{"MatriID": r.get("MatriID"), "Name": r.get("Name")} for r in sql_result["rows"] if r.get("Name")]
                    response_metadata = {"profile_candidates": profile_rows, "selected_profile": profile_rows[0] if profile_rows else None, "accumulated_filters": filters}

                    if sql_result["row_count"] == 0:
                        try:
                            from app.services.embedding_service import embed_text, build_profile_document
                            from app.services.vector_service import search_with_filters, get_client
                            get_client(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
                            timer.begin("ai_search")
                            yield f"data: {json.dumps({'type': 'status', 'step': 'ai_search'})}\n\n"
                            query_text = build_profile_document(filters)
                            query_vector = await embed_text(f"query: {message}. {query_text}", model_name=settings.EMBEDDING_MODEL)
                            vector_rows = search_with_filters(query_vector, filters=filters, limit=limit, host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
                            if vector_rows:
                                for row in vector_rows:
                                    from app.services.db_query_service import _add_photo_url
                                    _add_photo_url(row)
                                vector_result = {"sql": "vector_search", "rows": vector_rows, "row_count": len(vector_rows)}
                                profile_rows = [{"MatriID": r.get("MatriID"), "Name": r.get("Name")} for r in vector_rows if r.get("Name")]
                                response_metadata = {"profile_candidates": profile_rows, "selected_profile": profile_rows[0] if profile_rows else None, "accumulated_filters": filters}
                                timer.begin("format")
                                yield f"data: {json.dumps({'type': 'status', 'step': 'format'})}\n\n"
                                async for token, final in stream_format_db_result(message, vector_result, history=history, db=self.db):
                                    if token:
                                        collected_tokens.append(token)
                                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                                    if final:
                                        usage = accumulate_usage(usage, final.get("usage", {}))
                                        events.extend(final.get("events", []))
                                        reply_text = final.get("content", "".join(collected_tokens))
                            else:
                                notice = await format_db_notice(message, "No matching profiles found. Suggest trying a different city, caste, or age range.", history, db, "No matching profiles found.")
                                reply_text = notice.get("content", "No matching profiles found.")
                                yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                        except Exception as e:
                            logger.warning(f"Vector search fallback failed: {e}")
                            from app.services.db_query_service import _format_notice_safe
                            msg = await _format_notice_safe(message, "No matching profiles found. Suggest trying a different city, caste, or age range.", history, self.db, "No matching profiles found.")
                            reply_text = msg
                            yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                    elif sql_result["row_count"] > settings.MAX_ROWS_BEFORE_NARROW:
                        from app.services.db_query_service import _format_notice_safe
                        msg = await _format_notice_safe(message, f"The search found {sql_result['row_count']} results, too many to show. Ask the user to add more criteria.", history, self.db, f"The search found {sql_result['row_count']} results, too many to show at once. Please add more specific criteria.")
                        reply_text = msg
                        yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                    else:
                        timer.begin("format")
                        yield f"data: {json.dumps({'type': 'status', 'step': 'format'})}\n\n"
                        async for token, final in stream_format_db_result(message, sql_result, history=history, db=self.db):
                            if token:
                                collected_tokens.append(token)
                                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                            if final:
                                usage = accumulate_usage(usage, final.get("usage", {}))
                                events.extend(final.get("events", []))
                                reply_text = final.get("content", "".join(collected_tokens))
            else:
                if _is_profile_query(message, history):
                    timer.begin("think")
                    yield f"data: {json.dumps({'type': 'status', 'step': 'think'})}\n\n"
                    try:
                        notice = await format_db_notice(message, "No matching profiles found. Suggest trying a different city, caste, or age range.", history=history, db=self.db)
                        reply_text = notice.get("content", "No matching profiles found.")
                    except Exception:
                        reply_text = "No matching profiles found."
                    yield f"data: {json.dumps({'type': 'token', 'content': reply_text})}\n\n"
                else:
                    timer.begin("think")
                    yield f"data: {json.dumps({'type': 'status', 'step': 'think'})}\n\n"
                    async for token, final in stream_general_response(message, history=history, db=self.db):
                        if token:
                            collected_tokens.append(token)
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                        if final:
                            usage = accumulate_usage(usage, final.get("usage", {}))
                            events.extend(final.get("events", []))
                            reply_text = final.get("content", "".join(collected_tokens))

            if not reply_text:
                reply_text = "".join(collected_tokens) if collected_tokens else ""

            assistant_msg = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id, role="assistant",
                content=reply_text,
                metadata_json=json.dumps(response_metadata) if response_metadata else None,
                prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"], total_tokens=usage["total_tokens"],
            )
            await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            await self.db.commit()
            timer.log_summary(intent)
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv.id, 'message_id': assistant_msg.id, 'usage': usage})}\n\n"

        except Exception as e:
            logger.exception("Chat streaming error")
            try:
                await self.db.rollback()
            except Exception:
                pass
            reply_text = user_facing_error(e)
            yield f"data: {json.dumps({'type': 'error', 'content': reply_text})}\n\n"

    async def process_message(
        self, user_id: int, message: str, conversation_id: int | None = None
    ) -> dict:
        greeting_reply = _is_greeting_only(message)
        if greeting_reply and not conversation_id:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)
            _ = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id,
                role="user", content=message,
            )
            assistant_msg = await self.msg_repo.create(
                conversation_id=conv.id, user_id=user_id,
                role="assistant", content=greeting_reply,
            )
            await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))
            return {
                "reply": greeting_reply,
                "conversation_id": conv.id,
                "message_id": assistant_msg.id,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "request_id": "",
            }

        request_id = uuid.uuid4().hex
        if conversation_id:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if not conv or conv.user_id != user_id:
                raise ValueError("Conversation not found")
        else:
            n = settings.CHAT_TITLE_TRUNCATION
            title = message[:n] + ("..." if len(message) > n else "")
            conv = await self.conv_repo.create(user_id=user_id, title=title)

        history, conversation_context = await self._load_history(conv.id)

        user_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="user",
            content=message,
        )

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        events = []
        response_metadata = None
        try:
            result = await answer_database_question_hybrid(
                message, history=history, db=self.db,
                conversation_context=conversation_context,
            )
            if result.get("is_profile_search", False):
                request_type = "database"
            else:
                if _is_profile_query(message, history):
                    from app.services.llm_service import format_db_notice
                    try:
                        notice = await format_db_notice(
                            message,
                            "No matching profiles found. Suggest trying a different city, caste, or age range.",
                            history=history, db=self.db,
                        )
                        reply_text = notice.get("content", "No matching profiles found.")
                    except Exception:
                        reply_text = "No matching profiles found."
                    response_metadata = None
                    result = {
                        "content": reply_text,
                        "metadata": None,
                        "usage": {},
                        "events": [],
                    }
                else:
                    result = await get_general_response(
                        message, history=history, db=self.db
                    )
            reply_text = result["content"]
            response_metadata = result.get("metadata")
            events.extend(result.get("events", []))
            if result.get("usage"):
                u = result["usage"]
                usage = {
                    "prompt_tokens": usage["prompt_tokens"] + (u.get("prompt_tokens", 0) or 0),
                    "completion_tokens": usage["completion_tokens"] + (u.get("completion_tokens", 0) or 0),
                    "total_tokens": usage["total_tokens"] + (u.get("total_tokens", 0) or 0),
                }
        except Exception as e:
            logger.exception("Chat processing error")
            reply_text = user_facing_error(e)

        assistant_msg = await self.msg_repo.create(
            conversation_id=conv.id,
            user_id=user_id,
            role="assistant",
            content=reply_text,
            metadata_json=json.dumps(response_metadata) if response_metadata else None,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
        )

        await self.conv_repo.update(conv, updated_at=datetime.now(timezone.utc))

        return {
            "reply": reply_text,
            "conversation_id": conv.id,
            "message_id": assistant_msg.id,
            "usage": usage,
            "request_id": request_id,
        }

    async def get_conversation(self, user_id: int, conversation_id: int) -> dict:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        messages = await self.msg_repo.list_by_conversation(conversation_id)
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status,
            "messages": [
                {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }

    async def list_conversations(self, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        offset = (page - 1) * page_size
        items = await self.conv_repo.list_by_user_with_counts(user_id, limit=page_size, offset=offset)
        total = await self.conv_repo.count_by_user(user_id)
        for item in items:
            item["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
            item["updated_at"] = item["updated_at"].isoformat() if item["updated_at"] else None
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    async def delete_conversation(self, user_id: int, conversation_id: int) -> None:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        await self.conv_repo.delete(conv)

    async def update_conversation(
        self, user_id: int, conversation_id: int, title: str | None = None
    ) -> dict:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            raise ValueError("Conversation not found")
        updates = {}
        if title is not None:
            updates["title"] = title
        updates["updated_at"] = datetime.now(timezone.utc)
        conv = await self.conv_repo.update(conv, **updates)
        return {
            "id": conv.id,
            "title": conv.title,
            "status": conv.status,
            "updated_at": conv.updated_at.isoformat(),
        }
