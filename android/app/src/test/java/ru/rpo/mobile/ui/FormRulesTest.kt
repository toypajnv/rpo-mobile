package ru.rpo.mobile.ui

import java.time.LocalDateTime
import org.junit.Assert.assertEquals
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
    fun serverFieldsMapToCompletedUserStages() {
        val ids = savedStageIdsForFieldKeys(setOf("AT", "AU", "AV", "AY", "BC", "BE"))
        assertTrue("PREPARATION" in ids)
        assertTrue("TRANSFER_WORK" in ids)
        assertTrue("ACTUAL_WORK" in ids)
        assertTrue("EXTEND_WORK" in ids)
    }
}
