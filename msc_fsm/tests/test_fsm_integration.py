# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo.tests import TransactionCase
from odoo.exceptions import UserError


class TestFSMIntegration(TransactionCase):
    """Test cases for FSM integration with other modules"""

    def setUp(self):
        super(TestFSMIntegration, self).setUp()

        # Create test data
        self.partner = self.env["res.partner"].create(
            {
                "name": "Integration Test Customer",
                "email": "integration@test.com",
                "is_company": True,
            }
        )

        self.employee = self.env["hr.employee"].create(
            {
                "name": "Integration Test Technician",
            }
        )

        self.stage = self.env["msc.fsm.stage"].create(
            {
                "name": "Integration Test Stage",
                "code": "integration",
                "sequence": 1,
                "is_default": True,
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Test Service Product",
                "type": "service",
                "standard_price": 100.0,
                "list_price": 150.0,
            }
        )

    def test_sale_order_integration(self):
        """Test integration with sale orders"""
        # Create FSM order
        fsm_order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Integration test with sales",
            }
        )

        # Initially no sale order
        self.assertFalse(fsm_order.sale_order_ids)
        self.assertEqual(fsm_order.sale_count, 0)

        # Create sale order from FSM order
        result = fsm_order.action_create_sale_order()

        # Verify sale order creation
        self.assertTrue(fsm_order.sale_order_ids)
        sale_order = fsm_order.sale_order_ids[0]
        self.assertEqual(sale_order.partner_id, self.partner)
        self.assertEqual(sale_order.origin, f"Orden de Trabajo - {fsm_order.name}")

        # Verify sale order count
        self.assertTrue(fsm_order.sale_count >= 1)

        # Test viewing sale orders
        view_result = fsm_order.action_view_sale_orders()
        self.assertEqual(view_result["res_model"], "sale.order")

    def test_hr_employee_integration(self):
        """Test integration with HR employees"""
        fsm_order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "HR integration test",
                "person_ids": [(6, 0, [self.employee.id])],
            }
        )

        # Test technician assignment
        self.assertIn(self.employee, fsm_order.person_ids)

    def test_workflow_integration(self):
        """Test portal access functionality"""
        fsm_order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Portal access test",
            }
        )

        # Test access URL generation
        expected_url = f"/my/fsm/{fsm_order.id}"
        self.assertEqual(fsm_order.access_url, expected_url)

    def test_mail_integration(self):
        """Test mail thread integration"""
        fsm_order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Mail integration test",
            }
        )

        # Test that FSM order inherits mail functionality
        self.assertTrue(hasattr(fsm_order, "message_post"))
        self.assertTrue(hasattr(fsm_order, "message_ids"))
        self.assertTrue(hasattr(fsm_order, "activity_ids"))

        # Test posting a message
        message = fsm_order.message_post(
            body="Test message for FSM order", subject="Test Subject"
        )

        self.assertTrue(message)
        self.assertIn(message, fsm_order.message_ids)

    def test_workflow_integration(self):
        """Test complete workflow integration"""
        fsm_order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Complete workflow test",
            }
        )

        # 1. Start work
        fsm_order.action_start_work()
        self.assertTrue(fsm_order.date_start)

        # 2. Create quotation
        fsm_order.action_create_sale_order()
        self.assertTrue(fsm_order.sale_order_ids)

        # 3. Finish work
        from datetime import timedelta

        # Ensure duration > 0 by artificially rolling back start time
        fsm_order.write({"date_start": fsm_order.date_start - timedelta(hours=2)})
        fsm_order.action_finish_work()
        self.assertTrue(fsm_order.date_end)

        # Verify all integrations work together
        self.assertTrue(fsm_order.duration > 0)
        self.assertEqual(fsm_order.sale_count, 1)
