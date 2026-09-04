from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerDomainCollect(models.Model):
    _name = "res.partner.domain.collect"
    _description = "Collected Email Domain"
    _order = "name"

    name = fields.Char(
        string="Email Domain",
        required=True,
        help="Email domain (e.g. 'example.com') whose contacts are considered "
        "to belong to the company.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Company",
        required=True,
        ondelete="cascade",
        domain="[('is_company', '=', True)]",
        index=True,
    )

    _name_uniq_constraint = models.Constraint(
        "UNIQUE(partner_id, name)",
        "This email domain is already collected for this company.",
    )

    @api.constrains("partner_id")
    def _check_partner_id_is_company(self):
        """Only companies may collect email domains."""
        for record in self:
            if record.partner_id and not record.partner_id.is_company:
                raise ValidationError(_("Only companies can collect email domains."))

    @staticmethod
    def _normalize_domain(domain):
        """Normalize a collected domain for storage and matching."""
        if not domain:
            return ""
        domain = domain.strip().lower()
        if domain.startswith("@"):
            domain = domain[1:]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.strip(".")

    @api.model_create_multi
    def create(self, vals_list):
        """Normalize the domains and refresh the stored suggestions."""
        for vals in vals_list:
            if vals.get("name"):
                vals["name"] = self._normalize_domain(vals["name"])
        res = super().create(vals_list)
        self.env["res.partner"].sudo()._recompute_suggestions()
        return res

    def write(self, vals):
        """Normalize the domain and refresh the stored suggestions."""
        if vals.get("name"):
            vals["name"] = self._normalize_domain(vals["name"])
        res = super().write(vals)
        self.env["res.partner"].sudo()._recompute_suggestions()
        return res

    def unlink(self):
        """Refresh the stored suggestions after removing a domain."""
        res = super().unlink()
        self.env["res.partner"].sudo()._recompute_suggestions()
        return res
