package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class StagesTest {
    @Test
    fun startWorkContainsTransferStartAndFinish() {
        val stage = stages.firstOrNull { it.id == "START_WORK" }
        assertNotNull(stage)
        stage!!
        assertEquals(StageKind.TRIPLE_DATETIME, stage.kind)
        assertEquals("AV", stage.first.key)
        assertEquals("AY", stage.second?.key)
        assertEquals("BC", stage.third?.key)
    }

    @Test
    fun removedStagesAreNotVisibleToWorker() {
        val visibleKeys = stages.flatMap { stage ->
            listOfNotNull(stage.first.key, stage.second?.key, stage.third?.key)
        }.toSet()

        listOf("AX", "BD", "BF", "BG", "BH").forEach { removed ->
            assertFalse("$removed must not be visible in the app", removed in visibleKeys)
        }
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
