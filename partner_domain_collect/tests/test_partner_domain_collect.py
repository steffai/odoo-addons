from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestPartnerDomainCollect(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.company = cls.partner_model.create(
            {"name": "Bareos GmbH", "is_company": True}
        )
        cls.env["res.partner.domain.collect"].create(
            {"name": "bareos.com", "partner_id": cls.company.id}
        )

    def test_potential_contacts(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        self.assertEqual(self.company._potential_contacts(), contact)

    def test_potential_contacts_subdomain(self):
        contact = self.partner_model.create(
            {"name": "Jane", "email": "jane@sub.bareos.com"}
        )
        self.assertEqual(self.company._potential_contacts(), contact)

    def test_potential_contacts_ignore_other_domain(self):
        self.partner_model.create({"name": "Max", "email": "max@other.com"})
        self.assertFalse(self.company._potential_contacts())

    def test_potential_contacts_excludes_parented_and_companies(self):
        self.partner_model.create(
            {
                "name": "Eve",
                "email": "eve@bareos.com",
                "parent_id": self.company.id,
            }
        )
        self.partner_model.create(
            {"name": "Bareos AG", "is_company": True, "email": "info@bareos.com"}
        )
        self.assertFalse(self.company._potential_contacts())

    def test_potential_contacts_includes_company_name(self):
        bob = self.partner_model.create(
            {"name": "Bob", "email": "bob@bareos.com", "company_name": "Some GmbH"}
        )
        self.assertIn(bob, self.company._potential_contacts())

    def test_website_fallback(self):
        company = self.partner_model.create(
            {"name": "ACME", "is_company": True, "website": "https://www.acme.com"}
        )
        contact = self.partner_model.create(
            {"name": "Alice", "email": "alice@acme.com"}
        )
        self.assertEqual(company._potential_contacts(), contact)

    def test_suggested_company(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        self.assertIn(self.company, contact.suggested_company_ids_bareos)

    def test_suggested_company_via_website(self):
        company = self.partner_model.create(
            {"name": "ACME", "is_company": True, "website": "https://acme.com"}
        )
        contact = self.partner_model.create(
            {"name": "Alice", "email": "alice@acme.com"}
        )
        self.assertIn(company, contact.suggested_company_ids_bareos)

    def test_suggested_company_multiple(self):
        company2 = self.partner_model.create({"name": "Bareos AG", "is_company": True})
        self.env["res.partner.domain.collect"].create(
            {"name": "bareos.org", "partner_id": company2.id}
        )
        contact = self.partner_model.create(
            {"name": "Jane", "email": "jane@bareos.org"}
        )
        self.assertIn(company2, contact.suggested_company_ids_bareos)

    def test_no_suggestion_for_parented_contact(self):
        contact = self.partner_model.create(
            {
                "name": "Eve",
                "email": "eve@bareos.com",
                "parent_id": self.company.id,
            }
        )
        self.assertFalse(contact.suggested_company_ids_bareos)

    def test_domain_normalized(self):
        record = self.env["res.partner.domain.collect"].create(
            {"name": "  WWW.Bareos.ORG ", "partner_id": self.company.id}
        )
        self.assertEqual(record.name, "bareos.org")

    def test_domain_collect_requires_company(self):
        person = self.partner_model.create({"name": "Jane"})
        with self.assertRaises(ValidationError):
            self.env["res.partner.domain.collect"].create(
                {"name": "bareos.com", "partner_id": person.id}
            )

    def test_extract_website_domain(self):
        self.assertEqual(
            self.partner_model._extract_domain_from_website("https://www.example.com/"),
            "example.com",
        )
        self.assertEqual(
            self.partner_model._extract_domain_from_website("www.example.com"),
            "example.com",
        )

    def test_wizard_assign(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        wizard = (
            self.env["partner.domain.collect.wizard"]
            .with_context(active_id=self.company.id)
            .create({})
        )
        self.assertIn(contact, wizard.contact_ids)
        wizard.action_assign()
        self.assertEqual(contact.parent_id, self.company)

    def test_wizard_assign_rejects_invalid_contacts(self):
        other = self.partner_model.create({"name": "Other", "email": "x@other.com"})
        wizard = (
            self.env["partner.domain.collect.wizard"]
            .with_context(active_id=self.company.id)
            .create({})
        )
        wizard.contact_ids = [(6, 0, [other.id])]
        with self.assertRaises(ValidationError):
            wizard.action_assign()
        self.assertFalse(other.parent_id)

    def test_assign_suggested_company(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        contact.suggested_company_id_bareos = self.company
        contact.action_assign_suggested_company()
        self.assertEqual(contact.parent_id, self.company)
        self.assertFalse(contact.suggested_company_id_bareos)

    def test_assign_selected_suggested_company(self):
        exact = self.partner_model.create({"name": "Bareos Sub", "is_company": True})
        self.env["res.partner.domain.collect"].create(
            {"name": "sub.bareos.com", "partner_id": exact.id}
        )
        contact = self.partner_model.create(
            {"name": "Jane", "email": "jane@sub.bareos.com"}
        )
        self.assertIn(exact, contact.suggested_company_ids_bareos)
        self.assertIn(self.company, contact.suggested_company_ids_bareos)
        # the user selects the other suggested company
        contact.with_context(
            suggested_company_id_selected_bareos=self.company.id
        ).action_assign_suggested_company()
        self.assertEqual(contact.parent_id, self.company)

    def test_assign_suggested_company_requires_suggested_company(self):
        other = self.partner_model.create({"name": "Other GmbH", "is_company": True})
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        contact.with_context(
            suggested_company_id_selected_bareos=other.id
        ).action_assign_suggested_company()
        # a company that is not suggested must not be assigned
        self.assertFalse(contact.parent_id)

    def test_assign_suggested_company_requires_company(self):
        person = self.partner_model.create({"name": "Jane"})
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        contact.with_context(
            suggested_company_id_selected_bareos=person.id
        ).action_assign_suggested_company()
        self.assertFalse(contact.parent_id)

    def test_reassign_company_does_not_overwrite_vat(self):
        company_a = self.partner_model.create(
            {"name": "A GmbH", "is_company": True, "vat": "DE123456789"}
        )
        company_b = self.partner_model.create({"name": "B GmbH", "is_company": True})
        contact = self.partner_model.create({"name": "John", "email": "john@x.com"})
        contact.parent_id = company_a.id
        self.assertEqual(contact.vat, "DE123456789")
        contact.parent_id = company_b.id
        # company B's VAT must not be overwritten by company A's VAT
        self.assertFalse(company_b.vat)
        # the contact's VAT is re-synced from the new parent (empty)
        self.assertFalse(contact.vat)

    def test_reassign_company_keeps_new_vat(self):
        company_a = self.partner_model.create(
            {"name": "A GmbH", "is_company": True, "vat": "DE111111111"}
        )
        company_b = self.partner_model.create(
            {"name": "B GmbH", "is_company": True, "vat": "DE222222222"}
        )
        contact = self.partner_model.create({"name": "John", "email": "john@x.com"})
        contact.parent_id = company_a.id
        contact.parent_id = company_b.id
        self.assertEqual(company_b.vat, "DE222222222")
        self.assertEqual(contact.vat, "DE222222222")

    def test_suggested_company_match_domain(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@sub.bareos.com"}
        )
        contact.suggested_company_id_bareos = self.company
        self.assertEqual(contact.suggested_company_match_domain_bareos, "bareos.com")

    def test_suggested_company_match_domain_empty(self):
        contact = self.partner_model.create({"name": "Max", "email": "max@other.com"})
        self.assertFalse(contact.suggested_company_match_domain_bareos)

    def test_suggested_company_preselected(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        self.assertEqual(contact.suggested_company_id_bareos, self.company)

    def test_suggested_company_sorted_alphabetically(self):
        exact = self.partner_model.create({"name": "Bareos Sub", "is_company": True})
        self.env["res.partner.domain.collect"].create(
            {"name": "sub.bareos.com", "partner_id": exact.id}
        )
        contact = self.partner_model.create(
            {"name": "Jane", "email": "jane@sub.bareos.com"}
        )
        self.assertIn(exact, contact.suggested_company_ids_bareos)
        # alphabetical order: "Bareos GmbH" < "Bareos Sub"
        self.assertEqual(contact.suggested_company_id_bareos, self.company)

    def test_no_preselection_without_suggestion(self):
        contact = self.partner_model.create({"name": "Max", "email": "max@other.com"})
        self.assertFalse(contact.suggested_company_id_bareos)

    def test_search_suggested_company_id(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        self.assertEqual(contact.suggested_company_ids_bareos, self.company)
        found_m2m = self.partner_model.search(
            [("suggested_company_ids_bareos", "!=", False)]
        )
        self.assertIn(contact, found_m2m)
        found = self.partner_model.search(
            [("suggested_company_id_bareos", "!=", False)]
        )
        self.assertIn(contact, found)
        found_exact = self.partner_model.search(
            [("suggested_company_id_bareos", "=", self.company.id)]
        )
        self.assertIn(contact, found_exact)

    def test_suggestions_recomputed_when_domain_added(self):
        contact = self.partner_model.create(
            {"name": "Alice", "email": "alice@acme.org"}
        )
        self.assertFalse(contact.suggested_company_ids_bareos)
        company = self.partner_model.create({"name": "ACME", "is_company": True})
        self.env["res.partner.domain.collect"].create(
            {"name": "acme.org", "partner_id": company.id}
        )
        self.assertIn(company, contact.suggested_company_ids_bareos)
        self.assertEqual(contact.suggested_company_id_bareos, company)

    def test_suggestions_computed_on_create(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        self.assertIn(self.company, contact.suggested_company_ids_bareos)

    def test_suggestions_recomputed_on_email_change(self):
        contact = self.partner_model.create({"name": "Sam", "email": "sam@other.com"})
        self.assertFalse(contact.suggested_company_ids_bareos)
        contact.email = "sam@bareos.com"
        self.assertIn(self.company, contact.suggested_company_ids_bareos)

    def test_suggestions_cleared_when_assigned(self):
        contact = self.partner_model.create({"name": "Sam", "email": "sam@bareos.com"})
        self.assertIn(self.company, contact.suggested_company_ids_bareos)
        contact.parent_id = self.company.id
        self.assertFalse(contact.suggested_company_ids_bareos)

    def test_suggested_company_count(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        self.assertEqual(contact.suggested_company_count_bareos, 1)
        other = self.partner_model.create({"name": "Max", "email": "max@other.com"})
        self.assertEqual(other.suggested_company_count_bareos, 0)

    def test_suggested_company_info(self):
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        contact.suggested_company_id_bareos = self.company
        self.assertEqual(
            contact.suggested_company_info_bareos,
            "1 option(s) \u00b7 matching domain: bareos.com",
        )

    def test_name_search_restricted_by_context(self):
        other_company = self.partner_model.create(
            {"name": "Other GmbH", "is_company": True}
        )
        contact = self.partner_model.create(
            {"name": "John", "email": "john@bareos.com"}
        )
        result = self.partner_model.with_context(
            suggested_company_ids_bareos=contact.suggested_company_ids_bareos.ids
        ).name_search("", limit=100)
        found_ids = [r[0] for r in result]
        self.assertIn(self.company.id, found_ids)
        self.assertNotIn(other_company.id, found_ids)

    def test_name_search_is_model_method(self):
        # name_search is called via RPC with empty positional args; it must be
        # an @api.model method or the call_kw dispatcher fails with
        # "IndexError: list index out of range".
        self.assertTrue(getattr(self.partner_model.name_search, "_api_model", False))
