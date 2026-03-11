# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFSMTechnicianNotification(TransactionCase):
    """Test que al asignar técnicos a una orden se genera el email de notificación."""

    def setUp(self):
        super().setUp()

        # Partner (cliente)
        self.partner = self.env["res.partner"].create(
            {
                "name": "Cliente Test Notif",
                "email": "cliente_notif@example.com",
                "is_company": True,
            }
        )

        # Etapa por defecto (reutilizar existente o crear)
        self.stage = self.env["msc.fsm.stage"].search(
            [("is_default", "=", True)], limit=1
        )
        if not self.stage:
            self.stage = self.env["msc.fsm.stage"].create(
                {
                    "name": "Nueva Notif",
                    "code": "new_notif",
                    "sequence": 1,
                    "is_default": True,
                    "is_closed": False,
                    "color": "#00FF00",
                }
            )

        # Usuario con email para el empleado 1
        self.user_tech1 = self.env["res.users"].create(
            {
                "name": "Técnico Uno",
                "login": "tech_one_notif",
                "email": "tech1_notif@example.com",
            }
        )
        self.employee1 = self.env["hr.employee"].create(
            {
                "name": "Técnico Uno",
                "user_id": self.user_tech1.id,
                "work_email": "tech1_notif@example.com",
            }
        )

        # Usuario con email para el empleado 2
        self.user_tech2 = self.env["res.users"].create(
            {
                "name": "Técnico Dos",
                "login": "tech_two_notif",
                "email": "tech2_notif@example.com",
            }
        )
        self.employee2 = self.env["hr.employee"].create(
            {
                "name": "Técnico Dos",
                "user_id": self.user_tech2.id,
                "work_email": "tech2_notif@example.com",
            }
        )

        # Empleado SIN email ni usuario (no debería recibir correo)
        self.employee_no_email = self.env["hr.employee"].create(
            {
                "name": "Técnico Sin Email",
            }
        )

    def test_email_sent_on_create_with_technicians(self):
        """Al crear una orden con técnicos, se genera un mail.mail por cada técnico con email."""
        mail_before = self.env["mail.mail"].search_count([])

        order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Orden con técnicos en creación",
                "person_ids": [(6, 0, [self.employee1.id, self.employee2.id])],
            }
        )

        mail_after = self.env["mail.mail"].search_count([])
        # Se deben haber creado al menos 2 correos (uno por técnico)
        self.assertGreaterEqual(
            mail_after - mail_before,
            2,
            "Se deberían haber generado al menos 2 correos al crear la orden con 2 técnicos.",
        )

        # Verificar que los correos van dirigidos a los emails correctos
        new_mails = self.env["mail.mail"].search(
            [], order="id desc", limit=mail_after - mail_before
        )
        recipients = new_mails.mapped("email_to")
        recipients_text = " ".join([r or "" for r in recipients])
        self.assertIn("tech1_notif@example.com", recipients_text)
        self.assertIn("tech2_notif@example.com", recipients_text)

    def test_email_sent_on_write_new_technician(self):
        """Al añadir un nuevo técnico a una orden existente, se genera email solo para el nuevo."""
        order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Orden sin técnicos",
            }
        )

        mail_before = self.env["mail.mail"].search_count([])

        # Asignar técnico 1
        order.write({"person_ids": [(4, self.employee1.id)]})

        mail_after = self.env["mail.mail"].search_count([])
        self.assertGreaterEqual(
            mail_after - mail_before,
            1,
            "Se debería haber generado al menos 1 correo al asignar un técnico.",
        )

        # Verificar destinatario
        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        self.assertIn("tech1_notif@example.com", new_mail.email_to or "")

    def test_no_email_for_existing_technician(self):
        """Si un técnico ya estaba asignado y se añade otro, solo se notifica al nuevo."""
        order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Orden con un técnico",
                "person_ids": [(6, 0, [self.employee1.id])],
            }
        )

        mail_before = self.env["mail.mail"].search_count([])

        # Añadir técnico 2 (employee1 ya estaba)
        order.write({"person_ids": [(4, self.employee2.id)]})

        mail_after = self.env["mail.mail"].search_count([])
        new_mails = self.env["mail.mail"].search(
            [], order="id desc", limit=mail_after - mail_before
        )
        recipients_text = " ".join([m.email_to or "" for m in new_mails])

        # Solo se notifica al técnico 2 (el nuevo), no al 1 (ya existente)
        self.assertIn("tech2_notif@example.com", recipients_text)
        self.assertNotIn(
            "tech1_notif@example.com",
            recipients_text,
            "No se debería notificar al técnico que ya estaba asignado.",
        )

    def test_no_email_for_technician_without_email(self):
        """Un técnico sin email ni usuario vinculado no genera correo."""
        mail_before = self.env["mail.mail"].search_count([])

        order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Orden con técnico sin email",
                "person_ids": [(6, 0, [self.employee_no_email.id])],
            }
        )

        mail_after = self.env["mail.mail"].search_count([])
        self.assertEqual(
            mail_after - mail_before,
            0,
            "No se debería generar correo para un técnico sin email.",
        )

    def test_email_subject_contains_order_name(self):
        """El asunto del correo contiene el nombre de la orden."""
        order = self.env["msc.fsm.order"].create(
            {
                "partner_id": self.partner.id,
                "description": "Orden para test de asunto",
                "person_ids": [(6, 0, [self.employee1.id])],
            }
        )

        new_mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        self.assertIn(
            order.name,
            new_mail.subject or "",
            "El asunto del correo debería contener el nombre de la orden.",
        )

