"""A fake `claude -p` for the behavioural runner tests: no model, no network.

Agent mode (no `--tools` flag): writes menu.py into the working folder and prints a stream-json
transcript that loads the project's copy of the skill. Judge mode (`--tools`): answers with verdicts
for the M/C ids it finds in the material on stdin. Behaviour is chosen by environment variables:
  FAKE_AGENT  edit (default) | error | slow_once (first call hangs, later calls edit)
  FAKE_JUDGE  agree (default: all met / absent) | fenced | critical | malformed | wrong_ids | tool
  FAKE_STATE  folder for the call counter and the last judge input
"""
import json
import os
import re
import sys
import time


def emit(**event):
    print(json.dumps(event), flush=True)


def state(name):
    folder = os.environ.get("FAKE_STATE")
    return os.path.join(folder, name) if folder else None


def agent(prompt):
    mode = os.environ.get("FAKE_AGENT", "edit")
    counter = state("agent_calls")
    calls = 0
    if counter:
        calls = int(open(counter).read()) if os.path.exists(counter) else 0
        with open(counter, "w") as fh:
            fh.write(str(calls + 1))
    if mode == "slow_once" and calls == 0:
        time.sleep(60)
    skill = os.path.join(os.getcwd(), ".claude", "skills", "telegram-bot-ui")
    emit(type="system", subtype="init", model="fake-model", tools=["Read", "Edit", "Write"])
    emit(type="assistant", message={"content": [{"type": "tool_use", "id": "t1", "name": "Skill",
                                                 "input": {"skill": "telegram-bot-ui"}}]})
    emit(type="user", message={"content": [{"type": "tool_result", "tool_use_id": "t1",
                                            "content": f"Base directory for this skill: {skill}\n\n# skill"}]})
    with open("menu.py", "w", encoding="utf-8") as fh:
        fh.write("MENU = ['Orders', 'Settings', 'Help']\n")
    emit(type="assistant", message={"content": [{"type": "tool_use", "id": "t2", "name": "Write",
                                                 "input": {"file_path": "menu.py", "content": "..."}}]})
    if mode == "error":
        emit(type="result", subtype="error_during_execution", is_error=True, result="usage limit reached")
        return
    emit(type="result", subtype="success", is_error=False, result="Added the menu. First line: " + prompt.splitlines()[0],
         usage={"input_tokens": 10, "output_tokens": 5})


def judge(material):
    mode = os.environ.get("FAKE_JUDGE", "agree")
    path = state("judge_input.txt")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(material)
    musts = re.findall(r"^- (M\d+):", material, re.M)
    crits = re.findall(r"^- (C\d+):", material, re.M)
    verdict = {"must": [{"id": m, "verdict": "met", "evidence": "fake"} for m in musts],
               "critical_failures": [{"id": c, "verdict": "absent", "evidence": "fake"} for c in crits]}
    emit(type="system", subtype="init", model="fake-judge", tools=[])
    if mode == "critical":
        verdict["critical_failures"][0]["verdict"] = "present"
    if mode == "wrong_ids":
        verdict["must"] = verdict["must"][:-1]
    if mode == "tool":
        emit(type="assistant", message={"content": [{"type": "tool_use", "id": "j1", "name": "Read",
                                                     "input": {"file_path": "x"}}]})
    text = json.dumps(verdict)
    if mode == "fenced":
        text = "Here you go:\n```json\n" + text + "\n```"
    if mode == "malformed":
        text = "Everything looks met to me, great work."
    emit(type="result", subtype="success", is_error=False, result=text, usage={"input_tokens": 3, "output_tokens": 2})


def main():
    data = sys.stdin.buffer.read().decode("utf-8")
    if "--tools" in sys.argv:
        judge(data)
    else:
        agent(data)


if __name__ == "__main__":
    main()
