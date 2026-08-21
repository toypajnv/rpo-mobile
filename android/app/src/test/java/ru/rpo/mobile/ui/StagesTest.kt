package ru.rpo.mobile.ui

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
        assertTrue(keys.containsAll(listOf("AT", "AU", "AV", "AY", "BC", "AZ", "BA", "BE", "RI")))
    }
}
