from markupsafe import Markup

from odoo import fields, models


class MailActivityMixin(models.AbstractModel):
    _inherit = "mail.activity.mixin"

    def _schedule_incoming_message_activity(
        self,
        user_field="user_id",
        summary="react to message",
        activity_type_xmlid="mail.mail_activity_data_todo",
    ):
        """Schedule or update a TODO activity on incoming messages.

        Called by base_automation server actions on incoming messages.
        Creates at most one such activity per record, assigned to the
        first responsible user (or unassigned if none).

        .. note::
            The lookup/create flow is not atomic at the database level.
            Under extreme concurrent load (rare in practice) duplicate
            activities could be created for the same record.

        :param user_field: name of the Many2one/Many2many field holding
            the responsible user(s), e.g. ``"user_id"``, ``"user_ids"``.
        :param summary: summary text for the activity (default ``"react to message"``).
        :param activity_type_xmlid: XML ID of the activity type
            (default ``"mail.mail_activity_data_todo"``).
        """
        activity_type = self.env.ref(activity_type_xmlid)
        today = fields.Date.context_today(self)
        for record in self:
            if user_field not in record._fields:
                continue
            existing = self.env["mail.activity"].search(
                [
                    ("res_model", "=", record._name),
                    ("res_id", "=", record.id),
                    ("activity_type_id", "=", activity_type.id),
                    ("summary", "=", summary),
                    ("automated", "=", True),
                ],
                limit=1,
            )
            if existing:
                note = Markup(existing.note or "")
                note += Markup(f"<p>{today}: updated</p>")
                existing.write({"date_deadline": today, "note": note})
            else:
                user = record[user_field][:1] or None
                kwargs = {}
                if user:
                    kwargs["user_id"] = user.id
                record.activity_schedule(
                    activity_type_xmlid,
                    summary=summary,
                    note=Markup(f"<p>{today}: created</p>"),
                    date_deadline=today,
                    **kwargs,
                )
