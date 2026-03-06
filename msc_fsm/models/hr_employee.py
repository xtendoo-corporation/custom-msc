# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    msc_fsm_service_product_id = fields.Many2one(
        "product.product",
        string="Producto Servicio FSM",
        domain="[('type', '=', 'service')]",
        help="Producto utilizado al facturar las horas de este empleado en las órdenes de trabajo FSM.",
    )
