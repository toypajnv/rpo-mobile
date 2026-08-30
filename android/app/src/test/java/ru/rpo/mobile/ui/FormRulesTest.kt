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
    fun serverFieldsMapOnlyFullyCompletedGroupedStages() {
        val partialIds = savedStageIdsForFieldKeys(setOf("AT", "AV", "AY", "BE"))
        assertFalse("PREPARATION" in partialIds)
        assertTrue("TRANSFER_WORK" in partialIds)
        assertFalse("ACTUAL_WORK" in partialIds)
        assertTrue("EXTEND_WORK" in partialIds)

        val completedIds = savedStageIdsForFieldKeys(setOf("AT", "AU", "AV", "AY", "BC", "BE"))
        assertTrue("PREPARATION" in completedIds)
        assertTrue("TRANSFER_WORK" in completedIds)
        assertTrue("ACTUAL_WORK" in completedIds)
        assertTrue("EXTEND_WORK" in completedIds)
    }

    @Test
    fun unchangedServerFieldIsNotSentAgain() {
        assertFalse(shouldSendStageField("29.08.2026 10:00", "", "29.08.2026 10:00", ""))
        assertTrue(shouldSendStageField("29.08.2026 10:00", "", "29.08.2026 11:00", ""))
        assertTrue(shouldSendStageField("29.08.2026 10:00", "Старый", "29.08.2026 10:00", "Новый"))
        assertTrue(shouldSendStageField(null, null, "29.08.2026 10:00", ""))
    }
}
