from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class PartnerDomainCollectWizard(models.TransientModel):
    _name = "partner.domain.collect.wizard"
    _description = "Assign contacts to a company by email domain"

    company_id = fields.Many2one(
        "res.partner",
        string="Company",
        required=True,
        readonly=True,
    )
    contact_ids = fields.Many2many(
        "res.partner",
        string="Contacts",
        domain="[('id', 'in', available_contact_ids)]",
    )
    available_contact_ids = fields.Many2many(
        "res.partner",
        compute="_compute_available_contact_ids",
    )

    @api.depends("company_id")
    def _compute_available_contact_ids(self):
        """Contacts that may belong to the selected company."""
        for wizard in self:
            wizard.available_contact_ids = (
                wizard.company_id._potential_contacts()
                if wizard.company_id
                else self.env["res.partner"]
            )

    @api.model
    def default_get(self, fields_list):
        """Preselect the company's potential contacts."""
        res = super().default_get(fields_list)
        company = self.env["res.partner"].browse(self.env.context.get("active_id"))
        if company:
            res["company_id"] = company.id
            res["contact_ids"] = [Command.set(company._potential_contacts().ids)]
        return res

    def action_assign(self):
        """Assign the selected contacts to the company.

        Only contacts that actually match the company's collected (or website)
        domains are assigned; anything else is rejected.
        """
        contacts = self.contact_ids
        company = self.company_id
        if not company.is_company:
            raise ValidationError(_("The selected partner is not a company."))
        invalid = contacts - company._potential_contacts()
        if invalid:
            raise ValidationError(
                _(
                    "%(count)s selected contact(s) do not match the company's "
                    "collected domains.",
                    count=len(invalid),
                )
            )
        contacts.write({"parent_id": company.id})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Assign contacts"),
                "message": _(
                    "%(count)s contact(s) assigned to %(company)s.",
                    count=len(contacts),
                    company=company.display_name,
                ),
                "type": "success",
                "sticky": False,
            },
        }
