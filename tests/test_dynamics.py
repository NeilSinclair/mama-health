import asyncio

from fakes import FakeLabeller, fake_respond

from mama_analysis.dynamics import check_dynamics, dynamics_all, dynamics_dir, quote_in
from mama_analysis.labellers import Prompt
from mama_analysis.schemas import DynamicsLLM, Pushback


def _dyn(final="My gut hurts today", pushes=()):
    return DynamicsLLM(
        final_sentiment_quote=final,
        final_sentiment="satisfied",
        pushbacks=[
            Pushback(turn=t, kind="objection", quote=q, reason="r", bot_adapted=False)
            for t, q in pushes
        ],
    )


def test_dynamics_dir(tmp_path):
    assert dynamics_dir(tmp_path, "gpt_luna") == tmp_path / "dynamics" / "gpt_luna"


def test_quote_in_ignores_case_quote_style_and_spacing():
    assert quote_in("“You’re not   hearing me…”", "Honestly. You're not hearing me... at all")
    assert not quote_in("you never listen", "You're not hearing me")
    assert not quote_in("   ", "anything")


def test_check_dynamics_flags_invented_quotes_and_non_user_turns(records):
    s1 = records[0]  # t1 user "My gut hurts today", t2 assistant
    ok = check_dynamics(s1, _dyn(pushes=[(1, "gut hurts")]))
    assert ok == {"final_quote_found": True, "pushback_ok": [True]}
    bad = check_dynamics(
        s1, _dyn(final="I feel great", pushes=[(2, "sorry"), (1, "made up"), (9, "gut")])
    )
    assert bad == {"final_quote_found": False, "pushback_ok": [False, False, False]}


def test_dynamics_all_caches_one_entry_per_session(records, tmp_path):
    lab = FakeLabeller(fake_respond)
    entries = asyncio.run(dynamics_all(records, lab, Prompt("dynamics_v1", "S", "sha"), tmp_path))
    assert set(entries) == {"s1", "s2"}
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s1.json", "s2.json"]
    dyn = DynamicsLLM.model_validate(entries["s2"].output)
    assert dyn.final_sentiment_quote == "Hola, me duele"
    assert entries["s2"].prompt_version == "dynamics_v1"
