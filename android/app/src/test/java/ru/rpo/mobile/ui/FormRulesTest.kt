package ru.rpo.mobile.ui

import java.time.LocalDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FormRulesTest {
    @Test
    fun august17CurrentDayIsAccepted() {
        val now = LocalDateTime.of(2026, 8, 17, 15, 0)
        val result = parseOperationalDateTime("17.08.2026", "14:30", now)
        assertNull(result.error)
        assertEquals(LocalDateTime.of(2026, 8, 17, 14, 30), result.value)
    }

    @Test
    fun futureActualEventIsRejectedWithClearMessage() {
        val now = LocalDateTime.of(2026, 8, 17, 15, 0)
        val result = parseOperationalDateTime("17.08.2026", "16:00", now)
        assertTrue(result.error!!.contains("будущем"))
    }

    @Test
    fun resumeRequiresComment() {
        assertEquals("Комментарий при возобновлении обязателен", resumeCommentError("RESUME_WORK", ""))
        assertNull(resumeCommentError("RESUME_WORK", "Работы можно продолжить"))
        assertNull(resumeCommentError("TRANSFER_WORK", ""))
    }

    @Test
    fun blankStageIsNotMarkedReady() {
        assertFalse(stageDataReady(FormState()))
    }

    @Test
    fun preparationCanBeSavedWithStartOnlyAndValidOptionalEnd() {
        val startOnly = FormState(primaryDate = "19.08.2026", primaryTime = "10:00")
        assertTrue(stageDataReady(startOnly))
        assertFalse(stageDataReady(startOnly.copy(secondaryDate = "19.08.2026")))
        assertFalse(stageDataReady(startOnly.copy(secondaryDate = "19.08.2026", secondaryTime = "09:59")))
        assertTrue(stageDataReady(startOnly.copy(secondaryDate = "19.08.2026", secondaryTime = "11:00")))
    }

    @Test
    fun resumeReadinessRequiresComment() {
        val resume = stages.first { it.id == "RESUME_WORK" }
        val base = FormState(stage = resume, primaryDate = "19.08.2026", primaryTime = "10:00")
        assertFalse(stageDataReady(base))
        assertTrue(stageDataReady(base.copy(comment = "Работы разрешено возобновить")))
    }

    @Test
    fun latinLettersAreRemovedFromManualText() {
        assertTrue(containsLatinLetters("Ivanov"))
        assertFalse(containsLatinLetters("Иванов И.И."))
        assertEquals("Иванов ", removeLatinLetters("Иванов Ivanov"))
        assertEquals("666666-СН", removeLatinLetters("666666-СНAB"))
    }

    @Test
    fun serverFieldsMapToCompletedUserStages() {
        val ids = savedStageIdsForFieldKeys(setOf("AT", "AV", "AY", "BE"))
        assertTrue("PREPARATION" in ids)
        assertTrue("TRANSFER_WORK" in ids)
        assertTrue("ACTUAL_WORK" in ids)
        assertTrue("EXTEND_WORK" in ids)
    }
}
