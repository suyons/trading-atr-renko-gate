"""Optional LLM veto on a Renko reversal signal — replaces the old ollama call.

Runtime-agnostic: the command to invoke comes from the env var FILTER_AGENT_CMD,
so the runtime stays swappable (Claude today, something else tomorrow):

    FILTER_AGENT_CMD="claude -p"          # Claude Code, headless
    FILTER_AGENT_CMD="ollama run mymodel" # or anything that reads a prompt arg

Unset / empty → filter disabled, every reversal is taken (pure deterministic
strategy). It is opt-in, so an existing deployment is unaffected until set.
The prompt is appended as the final argument; the agent must answer with one
word: ENTER or SKIP.

Fails OPEN: any error, timeout, or unclear reply → ENTER (don't skip). The
deterministic strategy already decided to trade; the filter only ever *removes*
trades, so if it's unavailable we fall back to the coded signal.
"""
import os
import re
import shlex
import subprocess

ENV_VAR = "FILTER_AGENT_CMD"


def runtime_cmd() -> str:
    return os.environ.get(ENV_VAR, "").strip()


def is_enabled() -> bool:
    # Opt-in: the filter runs only when FILTER_AGENT_CMD is set non-empty.
    return bool(runtime_cmd())


def _build_prompt(symbol, side, balance, unrealised_pnl, recent_bricks) -> str:
    lines = "\n".join(
        f"  brick {i + 1}: open={b['open']:.6g} close={b['close']:.6g} dir={b['direction']}"
        for i, b in enumerate(recent_bricks)
    )
    seq = " ".join("U" if b["direction"] == "up" else "D" for b in recent_bricks)
    return (
        f"You are a trading signal filter. A deterministic ATR-Renko strategy just "
        f"flagged a {side} entry for {symbol} on a brick-direction reversal.\n\n"
        f"Account balance: {balance:.2f} USDT\n"
        f"Open uPnL on {symbol}: {unrealised_pnl:.2f} USDT\n\n"
        f"Recent Renko bricks (oldest to newest), direction sequence: {seq}\n{lines}\n\n"
        f"A FALSE signal is a reversal produced by sideways chop: many alternating "
        f"up/down bricks with no sustained trend. A REAL signal is a clean reversal "
        f"that breaks a run of same-direction bricks.\n\n"
        f"Reply with exactly one word: ENTER to take the trade, or SKIP if this is "
        f"a likely false (chop) signal."
    )


def should_skip(symbol, side, balance, unrealised_pnl, recent_bricks, timeout=90) -> bool:
    """True iff the filter judges this reversal a false signal that should be skipped."""
    if not is_enabled():
        return False
    if len(recent_bricks) < 3:
        return False  # not enough context to judge

    cmd = runtime_cmd()
    if not cmd:
        return False
    prompt = _build_prompt(symbol, side, balance, unrealised_pnl, recent_bricks)
    try:
        result = subprocess.run(
            shlex.split(cmd) + [prompt],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception:
        return False  # fail open
    if result.returncode != 0:
        return False  # fail open

    # Agents may reason before concluding, so take the LAST ENTER/SKIP token.
    matches = re.findall(r"\b(ENTER|SKIP)\b", result.stdout.upper())
    return bool(matches) and matches[-1] == "SKIP"
