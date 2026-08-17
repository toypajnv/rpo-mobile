package ru.rpo.mobile.ui

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
