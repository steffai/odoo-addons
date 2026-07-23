from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "automation_workflow_bareos")
class TestIncomingActivity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.activity_todo = cls.env.ref("mail.mail_activity_data_todo")

        cls.user1 = cls.env["res.users"].create(
            {
                "name": "User One",
                "login": "user1",
                "email": "user1@test.com",
            }
        )
        cls.user2 = cls.env["res.users"].create(
            {
                "name": "User Two",
                "login": "user2",
                "email": "user2@test.com",
            }
        )

        cls.partner_portal = cls.env["res.partner"].create(
            {
                "name": "Portal Partner",
                "email": "portal@test.com",
                "partner_share": True,
            }
        )

        cls.lead = cls.env["crm.lead"].create(
            {
                "name": "Test Lead",
                "user_id": cls.user1.id,
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.env["res.partner"]
                .create({"name": "SO Partner"})
                .id,
                "user_id": cls.user1.id,
            }
        )
        cls.purchase_order = cls.env["purchase.order"].create(
            {
                "partner_id": cls.env["res.partner"]
                .create({"name": "PO Partner"})
                .id,
                "user_id": cls.user1.id,
            }
        )
        cls.account_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "partner_id": cls.env["res.partner"]
                .create({"name": "AM Partner"})
                .id,
                "invoice_user_id": cls.user1.id,
                "journal_id": cls.env["account.journal"]
                .create({"name": "Test Journal", "type": "general"})
                .id,
            }
        )
        cls.project = cls.env["project.project"].create({"name": "Test Project"})
        cls.task = cls.env["project.task"].create(
            {
                "name": "Test Task",
                "project_id": cls.project.id,
                "user_ids": [(6, 0, [cls.user1.id, cls.user2.id])],
            }
        )

    def _assert_activity(self, record, note_start, exists=True):
        domain = [
            ("res_model", "=", record._name),
            ("res_id", "=", record.id),
            ("activity_type_id", "=", self.activity_todo.id),
            ("summary", "=", "react to message"),
        ]
        activities = self.env["mail.activity"].search(domain)
        if exists:
            self.assertEqual(len(activities), 1)
            self.assertIn(note_start, activities.note)
        else:
            self.assertFalse(activities)

    def _assert_no_activity(self, record):
        self._assert_activity(record, "", exists=False)

    def test_crm_lead(self):
        self.lead._schedule_incoming_message_activity()
        self._assert_activity(self.lead, "<p>2")

    def test_sale_order(self):
        self.sale_order._schedule_incoming_message_activity()
        self._assert_activity(self.sale_order, "<p>2")

    def test_purchase_order(self):
        self.purchase_order._schedule_incoming_message_activity()
        self._assert_activity(self.purchase_order, "<p>2")

    def test_account_move(self):
        self.account_move._schedule_incoming_message_activity(
            user_field="invoice_user_id"
        )
        self._assert_activity(self.account_move, "<p>2")

    def test_project_task(self):
        self.task._schedule_incoming_message_activity(user_field="user_ids")
        self._assert_activity(self.task, "<p>2")

    def test_dedup(self):
        self.lead._schedule_incoming_message_activity()
        self._assert_activity(self.lead, "<p>2")

        self.lead._schedule_incoming_message_activity()
        self._assert_activity(self.lead, "<p>2")
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", self.lead.id),
                ("activity_type_id", "=", self.activity_todo.id),
                ("summary", "=", "react to message"),
            ]
        )
        self.assertEqual(len(activities), 1)

    def test_manual_activity_not_overwritten(self):
        manual_activity = self.env["mail.activity"].create(
            {
                "res_model_id": self.env["ir.model"]._get("crm.lead").id,
                "res_id": self.lead.id,
                "activity_type_id": self.activity_todo.id,
                "summary": "react to message",
                "user_id": self.user1.id,
                "automated": False,
            }
        )
        manual_activity.write({"note": "<p>manual note</p>"})
        self.lead._schedule_incoming_message_activity()
        domain = [
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", self.lead.id),
            ("activity_type_id", "=", self.activity_todo.id),
            ("summary", "=", "react to message"),
        ]
        activities = self.env["mail.activity"].search(domain)
        self.assertEqual(len(activities), 2)
        manual = activities.filtered(lambda a: not a.automated)
        automated = activities.filtered(lambda a: a.automated)
        self.assertEqual(manual.id, manual_activity.id)
        self.assertIn("manual note", manual.note)
        self.assertTrue(automated)

    def test_unknown_user_field(self):
        self.lead._schedule_incoming_message_activity(user_field="nonexistent_field")
        self._assert_no_activity(self.lead)

    def test_no_responsible_user(self):
        lead_no_user = self.env["crm.lead"].create(
            {
                "name": "Lead No User",
                "user_id": False,
            }
        )
        lead_no_user._schedule_incoming_message_activity()
        self._assert_activity(lead_no_user, "<p>2")

    def test_no_responsible_user_dedup(self):
        lead_no_user = self.env["crm.lead"].create(
            {
                "name": "Lead No User",
                "user_id": False,
            }
        )
        lead_no_user._schedule_incoming_message_activity()
        self._assert_activity(lead_no_user, "<p>2")
        lead_no_user._schedule_incoming_message_activity()
        self._assert_activity(lead_no_user, "<p>2")
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", lead_no_user.id),
                ("activity_type_id", "=", self.activity_todo.id),
                ("summary", "=", "react to message"),
            ]
        )
        self.assertEqual(len(activities), 1)

    def test_no_responsible_user_m2m(self):
        task_no_user = self.env["project.task"].create(
            {
                "name": "Task No User",
                "project_id": self.project.id,
                "user_ids": False,
            }
        )
        task_no_user._schedule_incoming_message_activity(user_field="user_ids")
        self._assert_activity(task_no_user, "<p>2")

    def test_sale_order_no_user(self):
        so_no_user = self.env["sale.order"].create(
            {
                "partner_id": self.env["res.partner"]
                .create({"name": "SO No User Partner"}).id,
                "user_id": False,
            }
        )
        so_no_user._schedule_incoming_message_activity()
        self._assert_activity(so_no_user, "<p>2")

    def test_end_to_end_via_automation(self):
        model = self.env.ref("crm.model_crm_lead")
        automation = self.env["base.automation"].create(
            {
                "name": "Test Incoming Activity (CRM Lead)",
                "trigger": "on_message_received",
                "model_id": model.id,
                "active": True,
            }
        )
        self.env["ir.actions.server"].create(
            {
                "name": "Create Activity on Incoming Message (CRM Lead)",
                "model_id": model.id,
                "state": "code",
                "code": "record._schedule_incoming_message_activity(user_field='user_id')",
                "base_automation_id": automation.id,
            }
        )

        self.lead.message_post(
            body="Test message from portal user",
            author_id=self.partner_portal.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        self._assert_activity(self.lead, "<p>2")

    def test_end_to_end_internal_user_no_activity(self):
        model = self.env.ref("crm.model_crm_lead")
        automation = self.env["base.automation"].create(
            {
                "name": "Test Incoming Activity (CRM Lead)",
                "trigger": "on_message_received",
                "model_id": model.id,
                "active": True,
            }
        )
        self.env["ir.actions.server"].create(
            {
                "name": "Create Activity on Incoming Message (CRM Lead)",
                "model_id": model.id,
                "state": "code",
                "code": "record._schedule_incoming_message_activity(user_field='user_id')",
                "base_automation_id": automation.id,
            }
        )

        self.lead.message_post(
            body="Test message from internal user",
            author_id=self.user1.partner_id.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        self._assert_no_activity(self.lead)

    def test_custom_summary(self):
        custom_summary = "custom follow-up"
        self.lead._schedule_incoming_message_activity(summary=custom_summary)
        domain = [
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", self.lead.id),
            ("summary", "=", custom_summary),
        ]
        activities = self.env["mail.activity"].search(domain)
        self.assertEqual(len(activities), 1)

    def test_custom_activity_type(self):
        self.lead._schedule_incoming_message_activity(
            activity_type_xmlid="mail.mail_activity_data_call"
        )
        domain = [
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", self.lead.id),
            ("activity_type_id", "=", self.env.ref("mail.mail_activity_data_call").id),
            ("summary", "=", "react to message"),
        ]
        activities = self.env["mail.activity"].search(domain)
        self.assertEqual(len(activities), 1)

    def test_custom_summary_dedup(self):
        custom_summary = "custom follow-up"
        self.lead._schedule_incoming_message_activity(summary=custom_summary)
        self.lead._schedule_incoming_message_activity(summary=custom_summary)
        domain = [
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", self.lead.id),
            ("summary", "=", custom_summary),
        ]
        activities = self.env["mail.activity"].search(domain)
        self.assertEqual(len(activities), 1)

    def test_custom_activity_type_dedup(self):
        self.lead._schedule_incoming_message_activity(
            activity_type_xmlid="mail.mail_activity_data_call"
        )
        self.lead._schedule_incoming_message_activity(
            activity_type_xmlid="mail.mail_activity_data_call"
        )
        domain = [
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", self.lead.id),
            ("activity_type_id", "=", self.env.ref("mail.mail_activity_data_call").id),
            ("summary", "=", "react to message"),
        ]
        activities = self.env["mail.activity"].search(domain)
        self.assertEqual(len(activities), 1)
