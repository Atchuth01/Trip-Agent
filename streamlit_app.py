
import streamlit as st
import json
from openai import BadRequestError
from agent import (
    client, MODEL, build_system_prompt, TOOLS, execute_tool,
    _extract_failed_tool_call, _coerce_args,
)

st.set_page_config(page_title="TripAgent", page_icon="🧳", layout="centered")

st.title("🧳 TripAgent")
st.caption("An autonomous travel-planning agent — describe a trip, it plans it.")

query = st.text_input(
    "Describe your trip",
    placeholder="Plan a 3-day trip from Hyderabad to Goa in August under ₹20,000",
)

run = st.button("Plan my trip", type="primary")

if run and query.strip():
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": query},
    ]
    final_text = None

    with st.status("Agent is working...", expanded=True) as status:
        for turn in range(6):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    max_tokens=2000,
                    tools=TOOLS,
                    messages=messages,
                )
            except BadRequestError as e:
       
                tool_name, raw_args = _extract_failed_tool_call(e)
                if tool_name is None:
                    st.error(f"Unrecoverable model error: {e}")
                    break

                fixed_args = _coerce_args(tool_name, raw_args)
                st.write(f"⚠️ **{tool_name}** sent bad argument types "
                         f"`({json.dumps(raw_args)})` — auto-corrected to "
                         f"`({json.dumps(fixed_args)})`")
                try:
                    result = execute_tool(tool_name, fixed_args)
                except Exception as ex:
                    result = {"error": str(ex)}
                with st.expander("View raw tool result"):
                    st.json(result)

                fake_call_id = f"call_autofix_{turn}"
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": fake_call_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": json.dumps(fixed_args)},
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": fake_call_id,
                    "content": json.dumps(result),
                })
                continue

            msg = response.choices[0].message

            if msg.content and msg.content.strip():
                st.write(f"💭 {msg.content.strip()}")

            if not msg.tool_calls:
                final_text = msg.content or ""
                break

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                st.write(f"🔧 **{name}**`({json.dumps(args)})`")
                try:
                    result = execute_tool(name, args)
                except Exception as e:
                    result = {"error": str(e)}
                with st.expander("View raw tool result"):
                    st.json(result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

        status.update(label="Done", state="complete")

    if final_text:
        st.markdown("---")
        st.subheader("📋 Your Itinerary")
        st.markdown(final_text)
