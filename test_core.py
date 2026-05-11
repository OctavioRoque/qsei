"""
test_core.py
=============
Script de verificación rápida del núcleo.
Corre sin Flet para validar motor, DB y puntuación.

Uso:  python test_core.py
"""

import sys
import os

# Asegurar que el root del proyecto esté en el path
sys.path.insert(0, os.path.dirname(__file__))


def test_config():
    print("─── Config ───────────────────────────────")
    from config import GAME, DIFFICULTY_LEVELS, get_difficulty_label, SAVES_DIR
    print(f"  SAVES_DIR: {SAVES_DIR}")
    print(f"  score_base_easy: {GAME.score_base_easy}")
    label = get_difficulty_label(7)
    print(f"  Dificultad 7 → {label.label_es} ({label.color_hex})")
    print("  ✅ Config OK")


def test_math_utils():
    print("\n─── Math Utils ───────────────────────────")
    from engine.utils.math_utils import (
        is_close, relative_error, parse_function,
        has_sign_change, find_bracket, exercise_hash
    )
    assert is_close(2.0001, 2.0, tolerance=1e-3)
    assert not is_close(2.1, 2.0, tolerance=1e-3)
    print(f"  is_close: ✅")

    f = parse_function("x**3 - x - 2")
    assert abs(f(1.5) - (1.5**3 - 1.5 - 2)) < 1e-10
    print(f"  parse_function: ✅")

    assert has_sign_change(f, 1, 2)
    print(f"  has_sign_change: ✅")

    bracket = find_bracket(f)
    assert bracket is not None
    print(f"  find_bracket: {bracket} ✅")

    h = exercise_hash({"a": 1, "b": 2})
    print(f"  exercise_hash: {h} ✅")


def test_bisection_solver():
    print("\n─── Bisección Solver ─────────────────────")
    from engine.nonlinear.bisection import BisectionSolver
    from engine.utils.math_utils import parse_function

    solver = BisectionSolver()
    f = parse_function("x**2 - 4")
    result = solver.solve(f, 0, 3, tol=1e-6)

    print(f"  Converged: {result.converged}")
    print(f"  Root: {result.root:.8f}  (esperado: 2.0)")
    print(f"  Iteraciones: {result.num_iterations}")
    assert result.converged
    assert abs(result.root - 2.0) < 1e-5
    print("  ✅ Solver OK")


def test_bisection_validator():
    print("\n─── Bisección Validator ──────────────────")
    from engine.nonlinear.bisection import BisectionSolver, BisectionValidator
    from engine.utils.math_utils import parse_function

    solver = BisectionSolver()
    validator = BisectionValidator(tolerance=1e-4)
    f = parse_function("x**2 - 4")
    result = solver.solve(f, 0, 3)

    v_correct = validator.validate("2.0", result, {"ask_for": "root"})
    v_wrong   = validator.validate("3.5", result, {"ask_for": "root"})

    print(f"  Respuesta correcta (2.0): is_correct={v_correct.is_correct}, "
          f"precision={v_correct.precision_score:.2f}")
    print(f"  Respuesta incorrecta (3.5): is_correct={v_wrong.is_correct}")
    print(f"  Feedback: {v_correct.feedback[:60]}...")
    assert v_correct.is_correct
    assert not v_wrong.is_correct
    print("  ✅ Validator OK")


def test_bisection_generator():
    print("\n─── Bisección Generator ──────────────────")
    from engine.nonlinear.bisection import BisectionGenerator

    gen = BisectionGenerator()
    for diff in [2, 5, 8]:
        bundle = gen.generate(diff)
        print(f"  Dificultad {diff}: tipo={bundle.exercise_type} "
              f"expr={bundle.params.get('expr')} "
              f"correcta={bundle.correct_answer}")
        assert bundle.hash != ""
        assert bundle.solver_result.converged
    print("  ✅ Generator OK")


def test_scorer():
    print("\n─── Scorer ───────────────────────────────")
    from engine.scoring.scorer import Scorer
    from engine.utils.base_solver import ValidationResult

    scorer = Scorer()
    v_correct = ValidationResult(
        is_correct=True, precision_score=1.0,
        student_value=2.0, expected_value=2.0,
        absolute_error=0.0, feedback="✅ Correcto"
    )
    v_wrong = ValidationResult(
        is_correct=False, precision_score=0.0,
        student_value=5.0, expected_value=2.0,
        absolute_error=3.0, feedback="❌ Incorrecto"
    )

    score_good = scorer.calculate(v_correct, difficulty=5, time_seconds=8, current_streak=4)
    score_bad  = scorer.calculate(v_wrong,   difficulty=5, time_seconds=30, current_streak=0)

    print(f"  Correcto (rápido, racha 4): {score_good.total} pts "
          f"(base={score_good.base}, rapid={score_good.time_bonus}, "
          f"racha={score_good.streak_bonus})")
    print(f"  Incorrecto: {score_bad.total} pts")
    assert score_good.total > 0
    assert score_bad.total == 0

    # XP → nivel
    lvl, xp_in, xp_needed = Scorer.level_from_xp(250)
    print(f"  250 XP → Nivel {lvl}, {xp_in}/{xp_needed} XP en nivel")
    print("  ✅ Scorer OK")


def test_database():
    print("\n─── Database ─────────────────────────────")
    # Usar DB de prueba en /tmp
    import tempfile, os
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp()) / "test.db"

    # Monkey-patch DB_PATH
    import config
    original = config.DB_PATH
    config.DB_PATH = tmp

    from storage.sqlite import database as db_mod
    db_mod.DB_PATH = tmp

    # Reinicializar singleton
    db_mod.DatabaseManager._instance = None
    manager = db_mod.DatabaseManager(db_path=tmp)
    print(f"  DB creada en {tmp}")

    row = manager.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
    assert row is not None, "Tabla players no existe"
    print("  Tabla players: ✅")

    row = manager.fetchone("SELECT COUNT(*) as cnt FROM achievements")
    print(f"  Logros sembrados: {row['cnt']} ✅")

    config.DB_PATH = original
    print("  ✅ Database OK")


def test_player_repository():
    print("\n─── PlayerRepository ─────────────────────")
    import tempfile
    from pathlib import Path
    import config
    from storage.sqlite import database as db_mod

    tmp = Path(tempfile.mkdtemp()) / "test2.db"
    config.DB_PATH = tmp
    db_mod.DB_PATH = tmp
    db_mod.DatabaseManager._instance = None
    db_mod.DatabaseManager(db_path=tmp)

    from storage.repositories.player_repository import PlayerRepository
    repo = PlayerRepository()

    player = repo.create_player("testuser", "Test User", avatar_id=0)
    print(f"  Creado: {player.display_name} (id={player.id})")
    assert player.level == 1
    assert player.xp == 0

    found = repo.get_player_by_username("testuser")
    assert found is not None
    assert found.id == player.id
    print("  get_player_by_username: ✅")

    repo.upsert_method_stats(player.id, "biseccion", True, 150, 12.5)
    stats = repo.get_method_stats(player.id, "biseccion")
    assert stats.attempts == 1
    assert stats.correct == 1
    print(f"  method_stats: attempts={stats.attempts} mastery={stats.mastery_pct:.0f}% ✅")

    streak = repo.update_streak(player.id, True)
    streak = repo.update_streak(player.id, True)
    assert streak.current == 2
    print(f"  streak: current={streak.current} ✅")

    new_record = repo.update_record(player.id, "biseccion", 5, 300, 15.0)
    assert new_record
    print("  record: ✅")

    achievements = repo.get_achievements(player.id)
    print(f"  achievements: {len(achievements)} disponibles ✅")

    unlocked = repo.unlock_achievement(player.id, "first_correct")
    assert unlocked
    unlocked_again = repo.unlock_achievement(player.id, "first_correct")
    assert not unlocked_again
    print("  unlock_achievement: ✅")
    print("  ✅ PlayerRepository OK")


def main():
    print("=" * 50)
    print("  TEST NÚCLEO - ¿Quién quiere ser Ingeniero?")
    print("=" * 50)
    tests = [
        test_config,
        test_math_utils,
        test_bisection_solver,
        test_bisection_validator,
        test_bisection_generator,
        test_scorer,
        test_database,
        test_player_repository,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n  ❌ FALLÓ {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"  Resultado: {passed}/{len(tests)} pruebas pasaron")
    if failed == 0:
        print("  🎉 ¡Todo OK! El núcleo funciona correctamente.")
    else:
        print(f"  ⚠️  {failed} prueba(s) fallaron.")
    print("=" * 50)


if __name__ == "__main__":
    main()
