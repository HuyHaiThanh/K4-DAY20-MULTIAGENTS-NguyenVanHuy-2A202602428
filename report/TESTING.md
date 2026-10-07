# Ki?m th? v? t?i l?p

## Harness ch?nh theo GUIDE

Tr?n Windows ch?y trong WSL ho?c Docker v? backend d?ng /bin/sh. D?ng m?i tr??ng `.venv-linux` ?? c?i `pip install -e .`. Kh?ng truy?n bi?n m?i tr??ng/key v?o shell c?a agent.

```bash
python -m pytest
python scripts/tour.py
python -m lab.runner --condition baseline --tasks learn --recursion-limit 40
python -m lab.runner --condition subagents --tasks learn --recursion-limit 40
python -m lab.curator
python -m lab.runner --condition skills-auto --tasks learn --recursion-limit 40
# Review skill, hypotheses commit, freeze commit/tag; sao l?u skills-auto-dev.
python -m lab.runner --condition baseline --tasks eval --recursion-limit 40
python -m lab.runner --condition subagents --tasks eval --recursion-limit 40
python -m lab.runner --condition skills-auto --tasks all --recursion-limit 40
python scripts/verify_freeze.py
python -m lab.compare
python scripts/check_breakdown.py
```

C?c l?nh API g?i d? li?u lab ??n OpenAI theo s? ??ng ? c?a ng??i d?ng v? ph?t sinh token. Model/nhi?t ?? ??c t? .env; kh?ng commit key. Kh?ng xem eval tr??c freeze v? kh?ng s?a tay skill.

## Ki?m ch?ng

Full suite Linux c? 85 test ??t ? acceptance/pytest-final-review.txt. Prompt curator sau review ??t 2/2 test ? acceptance/curator-review.txt. File test g?c ?? ???c tr? ??ng byte LF t? Git, kh?ng thay ??i n?i dung; metadata t?i acceptance/line-ending-repair.json. Grader ki?m tra SHA256 byte n?n CRLF c?a checkout Windows c? th? g?y false failure.

Metadata OpenAI, usage, th?i gian v? ?i?m th?t thu?c results/, b?ng do lab.compare sinh v? b?o c?o REPORT.md. Kh?ng d?ng benchmark extension thay k?t qu? ch?nh. Trace ch? c? lu?ng ch?nh, token c?ng c? subagent. L?i API c? th? thi?u usage; kh?ng coi token ghi nh?n l? to?n b? h?a ??n.

## Extension offline

Coordinator, worker/tools/queue v? cache gi? nguy?n thi?t k? ? COORDINATOR.md, WORKERS.md, TOOLS.md. Benchmark offline d?ng ScriptedChatModel: token synthetic, kh?ng ch?ng minh accuracy ho?c latency API th?t. AST interpreter c? ph?m vi gi?i h?n; queue/cache kh?ng persistence v? kh?ng ph?i OS sandbox.

```bash
python scripts/debug_system.py
python scripts/profile_system.py
python scripts/benchmark.py --output report/acceptance/benchmark-offline-final.json
python scripts/benchmark_cache.py
python scripts/redteam_curator.py
```

Ch? k?t qu? API OpenAI hi?n t?i ???c gi? v? d?ng trong b?o c?o; k?t qu? t? API c? ?? x?a.
