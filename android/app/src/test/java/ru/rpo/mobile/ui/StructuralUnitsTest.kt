package ru.rpo.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class StructuralUnitsTest {
    @Test
    fun structuralUnitListMatchesRequestedDepartments() {
        assertEquals(
            listOf("ЦДПН-1", "ЦДПН-2", "ЦДПН-3", "ЦДПН-4", "ЦППН-1", "ЦППН-2", "ЦСДиТГ", "ЦСиР", "ЦТОиРТ-1", "ЦТОиРТ-2"),
            structuralUnits,
        )
        assertNull(structuralUnitError("ЦДПН-1"))
        assertTrue(structuralUnitError("")!!.contains("Выберите"))
    }

    @Test
    fun approvalLabelsAreClearForFieldWorker() {
        assertEquals("Ожидает разрешения оператора", approvalStatusLabel("pending"))
        assertEquals("Работы можно проводить", approvalStatusLabel("approved"))
        assertEquals("Разрешение не требуется", approvalStatusLabel("not_required"))
    }
}
