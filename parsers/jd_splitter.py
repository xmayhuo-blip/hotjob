"""JD text splitter - splits combined description text into duties and requirements."""
import re

# Sentence-level keywords
_DUTY_KW = [r"负责", r"参与", r"协助", r"推动", r"跟进", r"完成", r"主导", r"规划",
            r"设计", r"开发", r"维护", r"支持", r"制定", r"输出", r"跟进", r"落地",
            r"推进", r"协调", r"对接", r"分析", r"研究", r"搭建", r"优化", r"处理"]
_REQ_KW = [r"具备", r"熟悉", r"掌握", r"要求", r"本科", r"硕士", r"博士", r"经验",
           r"熟练", r"了解", r"精通", r"学历", r"优先", r"能力", r"技能", r"英语",
           r"加分项", r"任职资格", r"我们需要"]

_DUTY_RE = re.compile(r"(?:" + "|".join(_DUTY_KW) + ")")
_REQ_RE = re.compile(r"(?:" + "|".join(_REQ_KW) + ")")
# Strong requirement markers that override duty keywords in mixed lines
_STRONG_REQ_RE = re.compile(r"(?:经验|熟悉|掌握|本科|硕士|博士|学历|优先|精通|熟练|英语|能力要求|任职要求|任职资格)")

def split_jd(text):
    """Split combined JD text into (duties, requirements).
    Returns (duty_text, req_text) where either may be empty."""
    if not text:
        return "", ""
    lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    duty_lines, req_lines = [], []
    for line in lines:
        # If line has explicit requirement header, mark as requirement
        if _REQ_RE.search(line) and not _DUTY_RE.search(line):
            req_lines.append(line)
        elif _REQ_RE.search(line) and _DUTY_RE.search(line):
            # Mixed line: prefer requirement if it has strong req markers
            if _STRONG_REQ_RE.search(line):
                req_lines.append(line)
            else:
                duty_lines.append(line)
        else:
            duty_lines.append(line)
    return "\n".join(duty_lines), "\n".join(req_lines)

def has_requirement_headers(text):
    """Check if text contains explicit requirement section headers."""
    return bool(re.search(r"(?:任职要求|岗位要求|职位要求|任职资格|我们需要你|我们希望你是|应聘要求)", text or ""))
