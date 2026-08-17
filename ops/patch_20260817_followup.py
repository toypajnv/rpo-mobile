from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Missing replacement anchor: {label}")
    return text.replace(old, new, 1)


write("android/app/src/test/java/ru/rpo/mobile/ui/StageProgressTest.kt", '''package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StageProgressTest {
    @Test
    fun savedStageCountIgnoresUnknownIds() {
        val saved = setOf("PREPARATION", "TRANSFER_WORK", "OLD_REMOVED_STAGE")
        assertEquals(2, savedStageCount(saved))
    }

    @Test
    fun switchingWithUnsavedChangesRequiresWarning() {
        val current = stages.first { it.id == "PREPARATION" }
        val target = stages.first { it.id == "TRANSFER_WORK" }

        assertTrue(shouldWarnBeforeStageSwitch(current, target, hasUnsavedChanges = true))
        assertFalse(shouldWarnBeforeStageSwitch(current, target, hasUnsavedChanges = false))
        assertFalse(shouldWarnBeforeStageSwitch(current, current, hasUnsavedChanges = true))
    }
}
''')

write("android/app/src/test/java/ru/rpo/mobile/ui/StagesTest.kt", '''package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class StagesTest {
    @Test
    fun transferAndActualWorkAreSeparateBlocks() {
        val transfer = stages.firstOrNull { it.id == "TRANSFER_WORK" }
        val actual = stages.firstOrNull { it.id == "ACTUAL_WORK" }

        assertNotNull(transfer)
        assertNotNull(actual)
        assertEquals(StageKind.DATETIME, transfer!!.kind)
        assertEquals("AV", transfer.first.key)
        assertNull(transfer.second)

        assertEquals(StageKind.RANGE_DATETIME, actual!!.kind)
        assertEquals("AY", actual.first.key)
        assertEquals("BC", actual.second?.key)
        assertNull(actual.third)
    }

    @Test
    fun removedStagesAreNotVisibleToWorker() {
        val visibleKeys = stages.flatMap { stage ->
            listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key)
        }.toSet()

        listOf("AX", "BD", "BF", "BG", "BH").forEach { removed ->
            assertFalse("$removed must not be visible in the app", removed in visibleKeys)
        }
        assertFalse(stages.any { it.id == "START_WORK" })
        assertFalse(stages.any { it.id == "FINISH_WORK" })
    }

    @Test
    fun stageEventKeysAreUniqueAcrossVisibleStages() {
        val keys = stages.flatMap { stage ->
            listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key)
        }
        assertEquals(keys.size, keys.toSet().size)
        assertTrue(keys.containsAll(listOf("AT", "AU", "AV", "AY", "BC", "AZ", "BA", "BE")))
    }
}
''')

stages = read("server/app/stages.py")
stages = replace_once(
    stages,
    '"BA": {"label": "Возобновление работ", "order": 70, "kind": "datetime", "after": "AZ"},',
    '"BA": {"label": "Возобновление работ", "order": 70, "kind": "datetime", "after": "AZ", "comment_required": True},',
    "BA comment_required",
)
stages = replace_once(
    stages,
    '"BC": {"label": "Фактическое завершение РПО", "order": 80, "kind": "datetime", "after": "AY"},',
    '"BC": {"label": "Фактическое окончание работ", "order": 80, "kind": "datetime", "after": "AY"},',
    "BC label",
)
write("server/app/stages.py", stages)

validation = read("server/app/services/validation.py")
validation = replace_once(
    validation,
    '''    if stage.get("comment_required") and len(payload.comment.strip()) < 3:\n        raise EventValidationError("Для остановки работ необходимо указать причину")\n''',
    '''    if stage.get("comment_required") and len(payload.comment.strip()) < 3:\n        if payload.field_key == "BA":\n            raise EventValidationError("Для возобновления работ необходимо указать комментарий")\n        raise EventValidationError("Для остановки работ необходимо указать причину")\n''',
    "comment validation message",
)
write("server/app/services/validation.py", validation)

test_api = read("server/tests/test_api.py")
test_api += '''\n\ndef test_resume_requires_comment_on_server():\n    with TestClient(app) as c:\n        r = c.post(\n            "/api/mobile/events",\n            json=event_payload(\n                client_event_id="44444444-4444-4444-4444-444444444444",\n                permit_number="НД-RESUME",\n                field_key="BA",\n                stage_label="Возобновление работ",\n                event_time="2026-08-17T05:00:00+00:00",\n                field_value="17.08.2026 10:00",\n                comment="",\n            ),\n        )\n        assert r.status_code == 422, r.text\n        assert "комментар" in r.json()["detail"].lower()\n'''
write("server/tests/test_api.py", test_api)

# One-shot helper: do not keep automation scaffolding in production source.
(ROOT / "ops/patch_20260817_followup.py").unlink(missing_ok=True)

print("Follow-up stage tests and server validation patched")
