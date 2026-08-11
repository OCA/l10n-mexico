from psycopg2.errors import UniqueViolation

from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

# Key counts published by SAT in the payroll complement schema (catNomina.xsd).
# The schema enumerates every valid key, so these numbers are the contract: if
# a catalog drifts, the module is no longer in sync with what a PAC validates
# against.
EXPECTED_COUNTS = {
    "l10n_mx_catalogs.c_banco": 106,
    "l10n_mx_catalogs.c_origen_recurso": 3,
    "l10n_mx_catalogs.c_periodicidad_pago": 11,
    "l10n_mx_catalogs.c_riesgo_puesto": 6,
    "l10n_mx_catalogs.c_tipo_contrato": 11,
    "l10n_mx_catalogs.c_tipo_deduccion": 115,
    "l10n_mx_catalogs.c_tipo_horas": 3,
    "l10n_mx_catalogs.c_tipo_incapacidad": 4,
    "l10n_mx_catalogs.c_tipo_jornada": 9,
    "l10n_mx_catalogs.c_tipo_nomina": 2,
    "l10n_mx_catalogs.c_tipo_otro_pago": 10,
    "l10n_mx_catalogs.c_tipo_percepcion": 48,
    "l10n_mx_catalogs.c_tipo_regimen": 13,
}


class TestSatNominaCatalogs(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Deduccion = cls.env["l10n_mx_catalogs.c_tipo_deduccion"]
        cls.Percepcion = cls.env["l10n_mx_catalogs.c_tipo_percepcion"]
        cls.Source = cls.env["l10n_mx_catalogs.nomina_catalog_source"]

    def test_catalog_counts(self):
        for model, expected in EXPECTED_COUNTS.items():
            with self.subTest(model=model):
                self.assertEqual(self.env[model].search_count([]), expected)

    def test_codes_keep_the_sat_string_form(self):
        """Keys travel in the XML as strings, padding included."""
        self.assertTrue(self.Percepcion.search([("code", "=", "001")]))
        self.assertTrue(self.Percepcion.search([("code", "=", "057")]))
        self.assertTrue(
            self.env["l10n_mx_catalogs.c_periodicidad_pago"].search(
                [("code", "=", "04")]
            )
        )
        # Not every catalog is zero padded: c_RiesgoPuesto is "1".."5" and "99".
        self.assertTrue(
            self.env["l10n_mx_catalogs.c_riesgo_puesto"].search([("code", "=", "1")])
        )
        # And some keys are not numbers at all.
        self.assertTrue(
            self.env["l10n_mx_catalogs.c_tipo_nomina"].search([("code", "=", "O")])
        )

    def test_expired_key_is_out_of_force_from_its_end_date(self):
        """SAT: an expired key cannot be used *from* its end date onwards."""
        key = self.Deduccion.search([("code", "=", "063")])
        self.assertTrue(key)
        self.assertEqual(str(key.date_end), "2026-03-01")

        self.assertTrue(key.is_in_force("2026-01-15"))
        self.assertTrue(key.is_in_force("2026-02-28"))
        self.assertFalse(key.is_in_force("2026-03-01"))
        self.assertFalse(key.is_in_force("2026-04-15"))

        in_force = self.Deduccion.search_in_force("2026-01-15")
        self.assertIn(key, in_force)
        self.assertNotIn(key, self.Deduccion.search_in_force("2026-04-15"))

    def test_key_is_not_in_force_before_it_starts(self):
        key = self.Percepcion.search([("code", "=", "057")])
        self.assertTrue(key)
        self.assertEqual(str(key.date_start), "2026-06-12")
        self.assertFalse(key.is_in_force("2026-01-15"))
        self.assertTrue(key.is_in_force("2026-06-12"))
        self.assertNotIn(key, self.Percepcion.search_in_force("2026-01-15"))

    def test_search_in_force_accepts_an_extra_domain(self):
        result = self.Deduccion.search_in_force(
            "2026-04-15", domain=[("code", "=", "063")]
        )
        self.assertFalse(result)

    def test_nothing_found_is_not_in_force(self):
        """An empty recordset must not answer "usable"."""
        self.assertFalse(self.Percepcion.browse().is_in_force("2026-01-15"))
        self.assertFalse(
            self.Percepcion.search([("code", "=", "no-existe")]).is_in_force()
        )

    def test_display_name(self):
        key = self.Percepcion.search([("code", "=", "001")])
        self.assertEqual(key.name, "Sueldos, Salarios  Rayas y Jornales")
        self.assertEqual(key.display_name, "001 - Sueldos, Salarios  Rayas y Jornales")

    def test_code_is_unique(self):
        with self.assertRaises(UniqueViolation) as caught, mute_logger("odoo.sql_db"):
            self.Percepcion.create({"code": "001", "name": "Duplicada"})
            self.Percepcion.flush_model()
        self.assertEqual(
            caught.exception.diag.constraint_name,
            "l10n_mx_catalogs_c_tipo_percepcion_code_uniq",
        )

    def test_bank_keeps_its_legal_name(self):
        bank = self.env["l10n_mx_catalogs.c_banco"].search([("code", "=", "002")])
        self.assertEqual(bank.name, "BANAMEX")
        self.assertEqual(
            bank.legal_name,
            "Banco Nacional de México, S.A., Institución de Banca Múltiple, "
            "Grupo Financiero Banamex",
        )

    def test_source_is_recorded_for_every_catalog(self):
        expected_models = {
            "c_Banco": "l10n_mx_catalogs.c_banco",
            "c_OrigenRecurso": "l10n_mx_catalogs.c_origen_recurso",
            "c_PeriodicidadPago": "l10n_mx_catalogs.c_periodicidad_pago",
            "c_RiesgoPuesto": "l10n_mx_catalogs.c_riesgo_puesto",
            "c_TipoContrato": "l10n_mx_catalogs.c_tipo_contrato",
            "c_TipoDeduccion": "l10n_mx_catalogs.c_tipo_deduccion",
            "c_TipoHoras": "l10n_mx_catalogs.c_tipo_horas",
            "c_TipoIncapacidad": "l10n_mx_catalogs.c_tipo_incapacidad",
            "c_TipoJornada": "l10n_mx_catalogs.c_tipo_jornada",
            "c_TipoNomina": "l10n_mx_catalogs.c_tipo_nomina",
            "c_TipoOtroPago": "l10n_mx_catalogs.c_tipo_otro_pago",
            "c_TipoPercepcion": "l10n_mx_catalogs.c_tipo_percepcion",
            "c_TipoRegimen": "l10n_mx_catalogs.c_tipo_regimen",
        }
        self.assertEqual(set(expected_models.values()), set(EXPECTED_COUNTS))
        self.assertEqual(
            {source.catalog: source.model for source in self.Source.search([])},
            expected_models,
        )
        for source in self.Source.search([]):
            with self.subTest(catalog=source.catalog):
                self.assertTrue(source.version)
                self.assertTrue(source.revision)

    def test_publication_date_is_present_where_sat_publishes_one(self):
        """c_RiesgoPuesto is the one sheet SAT ships without a date."""
        undated = self.Source.search([("publication_date", "=", False)])
        self.assertEqual(undated.mapped("catalog"), ["c_RiesgoPuesto"])

    def test_source_reflects_the_shipped_revision(self):
        deduccion = self.Source.search([("catalog", "=", "c_TipoDeduccion")])
        self.assertEqual(deduccion.version, "4.0")
        self.assertEqual(deduccion.revision, "4.0")
        self.assertEqual(str(deduccion.publication_date), "2026-06-12")
