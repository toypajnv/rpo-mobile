package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class UxRulesTest {
    @Test
    fun stoppedPermitAlwaysSuggestsResume() {
        val next = recommendedStage(setOf("PREPARATION", "TRANSFER_WORK"), "stopped")
        assertEquals("RESUME_WORK", next?.id)
    }

    @Test
    fun preparationLabelMovesFromStartToFinish() {
        val preparation = stages.first { it.id == "PREPARATION" }
        assertEquals(
            "Передать начало подготовки",
            contextualActionLabel(FormState(stage = preparation)),
        )
        assertEquals(
            "Передать окончание подготовки",
            contextualActionLabel(
                FormState(
                    stage = preparation,
                    primaryDate = "30.08.2026",
                    primaryTime = "10:00",
                )
            ),
        )
    }

    @Test
    fun nextStageIsFirstIncompleteRequiredStage() {
        assertEquals("ACTUAL_WORK", recommendedStage(setOf("PREPARATION", "TRANSFER_WORK"), "approved")?.id)
        assertNull(recommendedStage(requiredStages.map { it.id }.toSet(), "approved"))
    }
}
