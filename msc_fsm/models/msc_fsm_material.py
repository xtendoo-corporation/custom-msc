# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MscFsmMaterial(models.Model):
    _name = "msc.fsm.material"
    _description = "Material consumido en Orden de Trabajo"

    order_id = fields.Many2one(
        "msc.fsm.order",
        string="Orden de Trabajo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('type', '=', 'consu')]",
    )
    name = fields.Text(string="Descripción", required=True)
    quantity = fields.Float(
        string="Cantidad", default=1.0, required=True, digits="Product Unit of Measure"
    )
    uom_id = fields.Many2one(
        "uom.uom", string="UdM", related="product_id.uom_id", readonly=True
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.name = record.product_id.display_name
