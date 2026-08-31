package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.rpo.mobile.data.PermitApprovalSummary

class DecisionLockContractTest {
    @Test
    fun deniedSummaryCarriesStageAndReasonForFullPermitLock() {
        val denial = PermitApprovalSummary(
            status = "denied",
            label = "Проведение работ запрещено",
            denied_count = 1,
            denied_field_key = "AV",
            denied_stage = "Передача ОП к ОБПР",
            denied_reason = "Не выполнены меры безопасности",
        )

        assertEquals("denied", denial.status)
        assertEquals("AV", denial.denied_field_key)
        assertEquals("Передача ОП к ОБПР", denial.denied_stage)
        assertTrue(denial.denied_reason.contains("меры безопасности"))
    }
}
