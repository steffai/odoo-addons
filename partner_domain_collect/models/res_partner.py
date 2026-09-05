from odoo import _, api, fields, models
from odoo.tools.mail import email_domain_extract


class ResPartner(models.Model):
    _inherit = "res.partner"

    domain_collect_ids_bareos = fields.One2many(
        "res.partner.domain.collect",
        "partner_id",
        string="Domains",
        help="Domains that belong to that company. "
        "Persons can automatically be assigned to this company, "
        "when there Email domains matches one of this domains. "
        "When empty, the company website domain is used instead.",
    )

    suggested_company_ids_bareos = fields.Many2many(
        "res.partner",
        relation="res_partner_suggested_company_ids_bareos_rel",
        column1="partner_id",
        column2="suggested_company_id",
        string="Suggested companies",
        compute="_compute_suggested_company_ids_bareos",
        store=True,
        help="Companies whose domain matches the email address of this contact.",
    )

    suggested_company_id_bareos = fields.Many2one(
        "res.partner",
        string="Suggested company",
        compute="_compute_suggested_company_id_bareos",
        inverse="_inverse_suggested_company_id_bareos",
        search="_search_suggested_company_id_bareos",
        help="First suggested company whose domain matches "
        "this contact's email address.",
    )

    suggested_company_match_domain_bareos = fields.Char(
        string="Matching domain",
        compute="_compute_suggested_company_match_domain_bareos",
        help="Domain of the selected suggested company that matches this "
        "contact's email address.",
    )

    suggested_company_count_bareos = fields.Integer(
        string="Options",
        compute="_compute_suggested_company_count_bareos",
        help="Number of companies suggested for this contact.",
    )

    suggested_company_info_bareos = fields.Char(
        string="Suggested companies info",
        compute="_compute_suggested_company_info_bareos",
        help="Number of suggested companies and the matching domain, as text.",
    )

    potential_contact_count = fields.Integer(
        string="Potential Contacts",
        compute="_compute_potential_contact_count",
        help="Number of unassigned contacts whose email domain matches this "
        "company.",
    )

    ### DOMAIN HELPERS

    @staticmethod
    def _email_domain_matches_domain(email_domain, domain):
        """Check whether an extracted email domain belongs to a domain."""
        return bool(email_domain) and (
            email_domain == domain or email_domain.endswith("." + domain)
        )

    @staticmethod
    def _email_domain_matches(email, domain):
        """Check whether an email address belongs to the given (sub)domain."""
        if not email or not domain:
            return False
        return ResPartner._email_domain_matches_domain(
            email_domain_extract(email) or "", domain
        )

    @staticmethod
    def _extract_domain_from_website(website):
        """Extract the registrable domain from a website URL.

        ``https://www.example.com/path`` and ``www.example.com`` both become
        ``example.com``.
        """
        if not website:
            return ""
        domain = website.strip()
        if "://" in domain:
            domain = domain.split("://", 1)[1]
        domain = domain.split("/", 1)[0]
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.strip(".")

    def _get_domain_candidates(self):
        """Domains used to find potential contacts of this company.

        Prefers the collected domains; falls back to the domain derived from
        the website when none are collected.
        """
        self.ensure_one()
        domains = list(self.domain_collect_ids_bareos.mapped("name"))
        if not domains:
            domain = self._extract_domain_from_website(self.website)
            if domain:
                domains = [domain]
        return domains

    def _potential_contacts(self):
        """Contacts that potentially belong to this company.

        Contacts that are not companies and have no parent, whose email domain
        matches a collected (or website) domain of the company. Contacts with a
        ``company_name`` set are included as well - they may still be assigned
        to this company.
        """
        self.ensure_one()
        domains = self._get_domain_candidates()
        if not domains:
            return self.env["res.partner"]
        candidates = self.env["res.partner"].search(
            [
                "&",
                ("is_company", "=", False),
                "&",
                ("parent_id", "=", False),
                ("email", "!=", False),
            ]
        )
        return candidates.filtered(
            lambda candidate: any(
                self._email_domain_matches(candidate.email, domain)
                for domain in domains
            )
        )

    ### COMPUTES

    @api.depends("email", "is_company", "parent_id")
    def _compute_suggested_company_ids_bareos(self):
        """Suggest companies for contacts without a parent company.

        The domain -> company mapping is built once so the compute stays
        cheap even when it runs for many contacts at once (list views).
        """
        domain_map = {}
        for collect in self.env["res.partner.domain.collect"].search([]):
            if collect.partner_id.is_company:
                domain_map.setdefault(collect.name, set()).add(collect.partner_id.id)
        for company in self.env["res.partner"].search(
            [
                ("is_company", "=", True),
                ("website", "!=", False),
                ("domain_collect_ids_bareos", "=", False),
            ]
        ):
            domain = company._extract_domain_from_website(company.website)
            if domain:
                domain_map.setdefault(domain, set()).add(company.id)
        for partner in self:
            if partner.is_company or partner.parent_id or not partner.email:
                partner.suggested_company_ids_bareos = False
                continue
            email_domain = email_domain_extract(partner.email) or ""
            company_ids = set()
            for domain, ids in domain_map.items():
                if self._email_domain_matches_domain(email_domain, domain):
                    company_ids |= ids
            partner.suggested_company_ids_bareos = (
                self.env["res.partner"].browse(company_ids).sorted("name")
                if company_ids
                else False
            )

    @api.depends("domain_collect_ids_bareos.name", "website", "is_company")
    def _compute_potential_contact_count(self):
        """Number of unassigned contacts matching one of this company's domains."""
        for partner in self:
            if not partner.is_company:
                partner.potential_contact_count = 0
            else:
                partner.potential_contact_count = len(partner._potential_contacts())

    @api.depends("suggested_company_id_bareos", "email")
    def _compute_suggested_company_match_domain_bareos(self):
        """Domain of the selected suggested company that matches the email."""
        for partner in self:
            partner.suggested_company_match_domain_bareos = False
            company = partner.suggested_company_id_bareos
            if not company or not partner.email:
                continue
            email_domain = email_domain_extract(partner.email) or ""
            for domain in company._get_domain_candidates():
                if email_domain == domain or email_domain.endswith("." + domain):
                    partner.suggested_company_match_domain_bareos = domain
                    break

    @api.depends("suggested_company_ids_bareos")
    def _compute_suggested_company_count_bareos(self):
        """Number of companies suggested for this contact."""
        for partner in self:
            partner.suggested_company_count_bareos = len(
                partner.suggested_company_ids_bareos
            )

    @api.depends(
        "suggested_company_count_bareos", "suggested_company_match_domain_bareos"
    )
    def _compute_suggested_company_info_bareos(self):
        """Human-readable summary of the suggestions and the matching domain."""
        for partner in self:
            parts = []
            if partner.suggested_company_count_bareos:
                parts.append(f"{partner.suggested_company_count_bareos} option(s)")
            if partner.suggested_company_match_domain_bareos:
                parts.append(
                    f"matching domain: {partner.suggested_company_match_domain_bareos}"
                )
            partner.suggested_company_info_bareos = " \u00b7 ".join(parts)

    @api.model
    @api.readonly
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Restrict the suggested-company dropdown to the matching companies."""
        if "suggested_company_ids_bareos" in self.env.context:
            ids = self.env.context["suggested_company_ids_bareos"]
            domain = (domain or []) + [("id", "in", list(ids or []))]
        return super().name_search(name, domain, operator, limit)

    @api.depends("suggested_company_ids_bareos")
    def _compute_suggested_company_id_bareos(self):
        """Preselect the first suggested company (alphabetical order)."""
        for partner in self:
            partner.suggested_company_id_bareos = partner.suggested_company_ids_bareos[
                :1
            ]

    def _inverse_suggested_company_id_bareos(self):
        """The selection is a form-session helper; nothing to persist."""
        return True

    def _search_suggested_company_id_bareos(self, operator, value):
        """Forward searches on the computed field to the stored M2M field."""
        return [("suggested_company_ids_bareos", operator, value)]

    def _recompute_suggestions(self):
        """Recompute the stored suggestions of all unassigned contacts.

        Called when a collected domain or a company website changes, so
        existing contacts pick up new (or lose removed) suggestions. Runs in
        sudo so all contacts are considered regardless of the caller's access.
        """
        contacts = (
            self.env["res.partner"]
            .sudo()
            .search(
                [
                    ("is_company", "=", False),
                    ("parent_id", "=", False),
                    ("email", "!=", False),
                ]
            )
        )
        if contacts:
            contacts.modified(["email"])

    def write(self, vals):
        """Clear a stale synced VAT on parent change and refresh suggestions on
        website change."""
        if vals.get("parent_id"):
            # (Re)assigning a parent company: drop the contact's synced
            # commercial field (vat) first, so a stale value carried from a
            # previous parent is not propagated upstream to the new company
            # (which would overwrite its VAT). It is re-synced from the new
            # parent by _fields_sync.
            contacts = self.filtered(lambda p: not p.is_company)
            if contacts and len(contacts) == len(self) and "vat" not in vals:
                vals["vat"] = False
        res = super().write(vals)
        if "website" in vals:
            self.filtered("is_company")._recompute_suggestions()
        return res

    ### ACTIONS

    def action_view_potential_contacts(self):
        """Open the wizard listing the contacts that may belong to this company."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Potential Contacts"),
            "res_model": "partner.domain.collect.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_id": self.id},
        }

    def action_assign_suggested_company(self):
        """Assign the selected suggested company as the contact's parent.

        The button passes the currently selected company through the context,
        because the field itself is computed (with a no-op inverse) and would
        otherwise fall back to the first suggestion. Only a company that is
        actually suggested for this contact is assigned.
        """
        self.ensure_one()
        selected = self.env.context.get("suggested_company_id_selected_bareos")
        company = (
            self.env["res.partner"].browse(int(selected))
            if selected
            else self.suggested_company_id_bareos
        )
        if (
            company
            and company.is_company
            and company in self.suggested_company_ids_bareos
            and company != self
        ):
            self.parent_id = company.id
        return True
