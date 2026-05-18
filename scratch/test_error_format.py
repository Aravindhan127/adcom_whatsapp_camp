
import sys
import os

# Mock the response structure
responses = [
    {
        "error": "Message failed to send",
        "code": 100,
        "subcode": 201,
        "fbtrace_id": "ABC123XYZ"
    },
    {
        "error": "Rate limit exceeded",
        "code": 429,
        "fbtrace_id": "RATE_LIMIT_TRACE"
    },
    {
        "error": "Template not approved",
        "code": 132001
    },
    {
        "error": "Unknown error"
    },
    "String error from API"
]

def format_meta_error(res_data: dict) -> str:
    """
    Consistently format a Meta API error response for storage/display.
    Returns: "(Code:Subcode) Message [Trace: ID]"
    """
    if not isinstance(res_data, dict):
        return str(res_data)
        
    error_msg = res_data.get("error") or "Unknown Meta Error"
    code = res_data.get("code")
    subcode = res_data.get("subcode")
    trace_id = res_data.get("fbtrace_id")
    
    parts = []
    if code:
        if subcode:
            parts.append(f"{code}:{subcode}")
        else:
            parts.append(str(code))
    
    code_str = f"({', '.join(parts)}) " if parts else ""
    trace_str = f" [Trace: {trace_id}]" if trace_id else ""
    
    return f"{code_str}{error_msg}{trace_str}"

for res in responses:
    print(f"Input: {res}")
    print(f"Output: {format_meta_error(res)}")
    print("-" * 20)
