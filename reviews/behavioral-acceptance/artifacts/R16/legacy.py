"""Unchanged task-provided baseline, retained only for regression comparisons."""


def parse(response):
    return response["output"][0]["content"][0]["text"]


def append_rendered_text(history, text):
    history.append({"role": "assistant", "content": text})
