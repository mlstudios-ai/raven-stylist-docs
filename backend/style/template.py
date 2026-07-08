import json

# Authoritative schema for style-agent output. Used in two places:
# 1. Embedded as text in STYLE_SYSTEM_PROMPT so the model sees the contract.
# 2. Passed to the inference server as a json_schema response_format so the
#    grammar constrains decoding to schema-valid output (catches drift the
#    looser "json_object" mode lets through — extra recommendations, missing
#    analysis keys, mis-keyed pieces).
#
# Keep this dict as the single source of truth. Top-level documentation
# fields ($schema/$id/title) and the unused $definitions block were
# dropped — they have no effect on grammar compilation or model behaviour.
STYLE_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "required": ["intent", "context", "analysis", "recommendations"],
    "properties": {
        "intent": {
            "type": "object",
            "additionalProperties": False,
        },
        "context": {
            "type": "object",
            "additionalProperties": False,
        },
        "analysis": {
            "type": "object",
            "additionalProperties": False,
        },
        "recommendations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


STYLE_SYSTEM_PROMPT = f"""
<|SIGMOI_STYLE|>You are a style agent with expertise in fashion and personal styling.
Respond in strict structured JSON for external compatibility with the output schema:
SIGMOI_STYLE task. Strictly use output schema for style recommendation:

{json.dumps(STYLE_OUTPUT_SCHEMA, indent=2)}
"""

def build_use_cases(use_cases: list[str]):
    use_cases_str = "\n".join(f"      - {item}" for item in use_cases)
    return use_cases_str

def build_style_signals(aesthetic_tags: list[str], photo_attributes):
    aesthetic_tags_str = "\n".join(f"    - {item}" for item in aesthetic_tags)
    photo_attributes_str = "\n".join(f"    - {item}" for item in photo_attributes)
    return aesthetic_tags_str, photo_attributes_str

def build_conversation(conversation):
    return "\n".join(
        f"  - role: {msg['role']}\n    content: {msg['content']}" for msg in conversation
    )

def build_styles(styles):
    return "\n".join(
        f"  - label: {s['label']}\n    reason: {s['reason']}" for s in styles
    )

STYLE_USER_PROMPT_TEMPLATE = """
profile:
"""