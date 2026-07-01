from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


SENSITIVE_FIELDS = {
    "password", "confirmpassword", "parentpassword",
    "password_hash", "account_number",
}

DB_SCHEMA_HINT = """
Available MySQL tables and useful columns:

register:
MatriID, Name, Gender, Age, Maritalstatus, Religion, Caste, City, Dist, State,
Education, Occupation, Annualincome, Height, Mobile, Status, Regdate.

membershipplan:
plandisplayname, planamount, planduration, plannoofcontacts,
description1, description2, description3, description4, description5, description6, description7.

siteconfig:
Webname, Fromemail, ContactEmail, address, openingtime, contactusmobile1, reg_phone.

cms:
content, link, mobile, email, whatsapp, officetime.

successstory:
bridename, groomname, marriagedate, successmessage, approve.

testimonial:
bridename, groomname, marriagedate, successmessage, approve.

agents:
agent_id, full_name, mobile, email, address, city, state, pincode, joining_date,
status, notes, account_holder_name, bank_name, branch_name, upi_id.

agent_commissions:
commission_id, sale_id, agent_id, plan_id, sale_date, commission_percentage,
commission_amount, commission_status, eligible_date, payment_date, admin_remarks.

agent_customers:
customer_id, agent_id, customer_name, customer_mobile, customer_email, plan_id,
plan_name, customer_status, notes, created_at, updated_at.

agent_plan_assignments:
assignment_id, agent_id, plan_id, commission_percentage, status, created_at, updated_at.

agent_sales:
sale_id, sale_reference, customer_matri_id, customer_name, customer_mobile,
customer_email, agent_id, plan_id, plan_name, plan_amount, payment_status,
sale_status, sale_date, created_at.

agent_withdrawal_requests:
withdrawal_id, agent_id, requested_amount, available_balance, request_date,
status, admin_remarks, payment_date, created_at, updated_at.
""".strip()

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "jpg", "jpeg", "png", "txt"}
MAX_UPLOAD_SIZE_MB = 20
