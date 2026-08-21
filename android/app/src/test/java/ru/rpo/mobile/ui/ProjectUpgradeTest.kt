package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectUpgradeTest {
    @Test
    fun replacementStageIsOptionalAndDoesNotIncreaseRequiredProgress() {
        val replacement = stages.first { it.id == "REPLACEMENTS" }
        assertTrue(replacement.optional)
        assertEquals(StageKind.REPLACEMENTS, replacement.kind)
        assertEquals("RI", replacement.first.key)
        assertFalse(replacement in requiredStages)
        assertEquals(6, requiredStageCount)
        assertEquals(0, savedStageCount(setOf("REPLACEMENTS")))
    }

    @Test
    fun replacementRowsRoundTripAndRequireBothFields() {
        val rows = listOf(
            ReplacementEntry("Иванов И.И.", "электромонтёр"),
            ReplacementEntry("Петров П.П.", "слесарь"),
        )
        assertTrue(replacementsReady(rows))
        val encoded = encodeReplacements(rows)
        assertEquals(rows, decodeReplacements(encoded))
        assertFalse(replacementsReady(listOf(ReplacementEntry("Иванов И.И.", ""))))
    }

    @Test
    fun replacementStageReadinessUsesReplacementRows() {
        val stage = stages.first { it.id == "REPLACEMENTS" }
        assertFalse(stageDataReady(FormState(stage = stage)))
        assertTrue(stageDataReady(FormState(
            stage = stage,
            replacements = listOf(ReplacementEntry("Иванов И.И.", "машинист")),
        )))
    }
}
