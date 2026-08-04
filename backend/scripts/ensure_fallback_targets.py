import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.commercial_model import AIModel, AIProvider, AITaskRoute, AITaskTarget


async def main() -> None:
    async with AsyncSessionLocal() as db:
        ollama = (await db.execute(select(AIProvider).where(AIProvider.code == "ollama"))).scalar_one_or_none()
        if not ollama:
            print("ollama provider not found - start the app once to seed defaults first")
            return
        model = (await db.execute(
            select(AIModel).where(
                AIModel.provider_id == ollama.id,
                AIModel.external_id == "qwen2.5:7b-instruct",
            )
        )).scalar_one_or_none()
        if not model:
            print("qwen2.5:7b-instruct not found - start the app once to seed defaults first")
            return
        routes = (await db.execute(select(AITaskRoute))).scalars().all()
        for route in routes:
            target = (await db.execute(
                select(AITaskTarget).where(
                    AITaskTarget.route_id == route.id,
                    AITaskTarget.priority == 2,
                )
            )).scalar_one_or_none()
            if target:
                target.model_id = model.id
                target.enabled = True
                print(f"route={route.task_key} priority=2 ok -> qwen2.5:7b-instruct")
            else:
                db.add(AITaskTarget(route_id=route.id, model_id=model.id, priority=2, enabled=True))
                print(f"route={route.task_key} priority=2 added -> qwen2.5:7b-instruct")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
