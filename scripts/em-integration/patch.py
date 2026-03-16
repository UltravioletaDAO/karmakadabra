import re

with open("generate-soul.py", "r") as f:
    content = f.read()

bad_line = """- {{"inquisitive": "Ask lots of questions — you're naturally curious", "enthusiastic": "Use exclamations and hype — you're energetic!", "analytical": "Provide detailed analysis and explanations", "reactive": "Keep responses short and punchy", "conversational": "Balance questions with opinions naturally"}.get(tone, "Communicate authentically and naturally")}"""

replacement = """    tone_dict = {"inquisitive": "Ask lots of questions — you're naturally curious", "enthusiastic": "Use exclamations and hype — you're energetic!", "analytical": "Provide detailed analysis and explanations", "reactive": "Keep responses short and punchy", "conversational": "Balance questions with opinions naturally"}
    tone_msg = tone_dict.get(tone, "Communicate authentically and naturally")
    
    soul += f\"\"\"
## Communication Guidelines
- Write messages that average ~{int(avg_msg_len)} characters
- {tone_msg}"""

content = content.replace('    soul += f"""\n## Communication Guidelines\n- Write messages that average ~{int(avg_msg_len)} characters\n' + bad_line, replacement)

with open("generate-soul.py", "w") as f:
    f.write(content)
