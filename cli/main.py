"""Entrypoint for CityCare's command-line validation tools."""

from __future__ import annotations

import argparse

from cli.commands.prescription_chat import answer_question, run_repl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="citycare")
    commands = parser.add_subparsers(dest="command", required=True)

    prescription_chat = commands.add_parser(
        "prescription-chat",
        help="Ask grounded questions about one patient's retrieved prescription records.",
    )
    prescription_chat.add_argument("--patient-id", required=True, help="Patient ID used to scope retrieval.")
    prescription_chat.add_argument("--top-k", type=int, default=3, help="Maximum prescription records to retrieve.")
    prescription_chat.add_argument("--question", help="Ask one question instead of starting the interactive session.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command != "prescription-chat":
        return 1
    if args.top_k < 1:
        raise SystemExit("--top-k must be at least 1.")

    if args.question:
        result = answer_question(args.patient_id, args.question, args.top_k)
        print(f"Answer:\n{result.answer}\n\nRetrieved sources:\n{result.sources}")
        return 0

    run_repl(args.patient_id, args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
