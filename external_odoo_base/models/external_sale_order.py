# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools

import logging
_logger = logging.getLogger(__name__)

from dateutil.relativedelta import relativedelta
from datetime import datetime

class ExternalSaleOrder(models.Model):
    _name = 'external.sale.order'
    _description = 'External Sale Order'
    _order = 'create_date desc'
    
    name = fields.Char(        
        compute='_get_name',
        string='Nombre',
        store=False
    )
    
    @api.one        
    def _get_name(self):            
        for obj in self:
            obj.name = obj.external_id
                
    external_url = fields.Char(        
        compute='_get_external_url',
        string='External Url',
        store=False
    )
    
    @api.one        
    def _get_external_url(self):            
        for obj in self:
            if obj.external_source_id.id>0:
                if obj.external_id!=False:
                    obj.external_url = ''
                    if obj.external_source_id.type=='shopify':
                        obj.external_url = 'https://'+str(obj.external_source_id.url)+'/admin/orders/'+str(obj.external_id)
                    elif obj.external_source_id.type=='woocommerce':
                        obj.external_url = str(obj.external_source_id.url)+'wp-admin/post.php?post='+str(obj.external_id)+'&action=edit'                                    
    #fields
    external_id = fields.Char(
        string='External Id'
    )
    external_billing_address_id = fields.Many2one(
        comodel_name='external.address',
        string='Billing Address'
    )
    external_shipping_address_id = fields.Many2one(
        comodel_name='external.address',
        string='Shipping Address'
    )
    external_customer_id = fields.Many2one(
        comodel_name='external.customer',
        string='Customer'
    )    
    woocommerce_state = fields.Selection(
        [
            ('none', 'Ninguno'),
            ('pending', 'Pending Payment'),
            ('shipped', 'Shipped'),
            ('processing', 'Processing'),
            ('on-hold', 'On Hold'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded'),
            ('failed', 'Failed')
        ],
        string='Woocommerce State',
        default='none'
    )
    shopify_state = fields.Selection(
        [
            ('none', 'Ninguno'),
            ('pending', 'Pending'),
            ('authorized', 'Authorized'),
            ('paid', 'Paid'),
            ('partially_paid', 'Partially Paid'),
            ('refunded', 'Refunded'),
            ('partially_refunded', 'Partially Refunded'),
            ('voided', 'Voided'),            
        ],
        string='Shopify State',
        default='none'
    )
    date = fields.Datetime(
        string='Date'
    )    
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency'
    )
    external_source_id = fields.Many2one(
        comodel_name='external.source',
        string='Source'
    )
    external_source_type = fields.Char(
        compute='_get_external_source_type',
        store=False,
        string='Source Type'
    )            
    payment_transaction_id = fields.Many2one(
        comodel_name='payment.transaction',
        string='Payment Transaction'
    )
    lead_id = fields.Many2one(
        comodel_name='crm.lead',
        string='Lead'
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Pedido de venta'
    )    
    number = fields.Integer(
        string='Number'
    )
    total_price = fields.Monetary(
        string='Total Price'
    )
    subtotal_price = fields.Monetary(
        string='Subtotal Price'
    )
    total_tax = fields.Monetary(
        string='Total Tax'
    )
    total_discounts = fields.Monetary(
        string='Total Discounts'
    )
    total_line_items_price = fields.Monetary(
        string='Total Line Items Price'
    )    
    total_shipping_price = fields.Monetary(
        string='Total Shipping Price'
    )
    external_sale_order_discount_ids = fields.One2many('external.sale.order.discount', 'external_sale_order_id', string='Discounts', copy=True)
    external_sale_order_line_ids = fields.One2many('external.sale.order.line', 'external_sale_order_id', string='Lines', copy=True)
    external_sale_order_shipping_ids = fields.One2many('external.sale.order.shipping', 'external_sale_order_id', string='Shipping Lines', copy=True)
    
    @api.one        
    def _get_external_source_type(self):            
        for obj in self:
            if obj.external_source_id.id>0:
                obj.external_source_type = obj.external_source_id.type    
    
    @api.multi
    def action_run_multi(self):
        for obj in self:
            if obj.sale_order_id.id==0:
                obj.action_run()    

    @api.one
    def allow_create(self):
        return_item = False        
        #operations
        if self.external_source_id.id>0:
            if self.external_source_id.type=='woocommerce':
                if self.woocommerce_state in ['processing', 'shipped', 'completed']:
                    return_item = True
            elif self.external_source_id.type=='shopify':
                if self.shopify_state=='paid':
                    return_item = True
        #return
        return return_item
    
    @api.one
    def action_run(self):
        #allow_create
        allow_create_item = self.allow_create()[0]
        if allow_create_item==True:
            #actions        
            self.action_crm_lead_create()
            self.action_sale_order_create()
            self.action_sale_order_done()
            self.action_payment_transaction_create()
            self.action_crm_lead_win()
        #return
        return False        
            
    @api.one
    def action_crm_lead_create(self):
        if self.lead_id.id==0:
            if self.external_customer_id.id>0:
                if self.external_customer_id.partner_id.id>0:   
                    #date_deadline
                    current_date = datetime.today()
                    date_deadline = current_date + relativedelta(days=1)
                    #vals
                    crm_lead_vals = {
                        'external_sale_order_id': self.id,
                        'type': 'opportunity',
                        'name': str(self.external_source_id.type)+' '+str(self.number),
                        'team_id': 1,
                        'probability': 10,
                        'date_deadline': str(date_deadline.strftime("%Y-%m-%d %H:%I:%S"))
                    }
                    #user_id
                    if self.external_source_id.external_sale_order_user_id.id>0:
                        crm_lead_vals['user_id'] = self.external_source_id.external_sale_order_user_id.id
                    #create
                    crm_lead_obj = self.env['crm.lead'].sudo(self.create_uid).create(crm_lead_vals)
                    #update_partner_id
                    crm_lead_obj.partner_id = self.external_customer_id.partner_id.id
                    crm_lead_obj._onchange_partner_id()
                    # user_id (partner_id)
                    if self.external_source_id.external_sale_order_user_id.id > 0:
                        if crm_lead_obj.partner_id.user_id.id == 0:
                            crm_lead_obj.partner_id.user_id = self.external_source_id.external_sale_order_user_id.id
                    #lead_id
                    self.lead_id = crm_lead_obj.id                                        
        #return
        return False
        
    @api.one
    def action_sale_order_create(self):
        if self.sale_order_id.id==0:
            #allow_create_sale_order
            allow_create_sale_order = False
            #external_customer_id
            if self.external_customer_id.id>0:
                if self.external_customer_id.partner_id.id>0:
                    #external_billing_address_id
                    if self.external_billing_address_id.id>0:
                        if self.external_billing_address_id.partner_id.id>0:
                            #external_shipping_address_id
                            if self.external_shipping_address_id.id>0:
                                if self.external_shipping_address_id.partner_id.id>0:
                                    allow_create_sale_order = True
                                    #external_sale_order_line_ids               
                                    for external_sale_order_line_id in self.external_sale_order_line_ids:
                                        if external_sale_order_line_id.external_product_id.id==0:
                                            allow_create_sale_order = False
            #operations                
            if allow_create_sale_order==True:                        
                #vals
                sale_order_vals = {
                    'external_sale_order_id': self.id,
                    'state': 'draft',
                    'opportunity_id': self.lead_id.id,
                    'team_id': self.lead_id.team_id.id,
                    'partner_id': self.lead_id.partner_id.id,
                    'partner_invoice_id': self.external_billing_address_id.partner_id.id,
                    'partner_shipping_id': self.external_shipping_address_id.partner_id.id,
                    'date_order': str(self.date),
                    'show_total': True,
                    'origin': str(self.lead_id.name)                                                
                }
                #user_id
                if self.lead_id.user_id.id>0:
                    sale_order_vals['user_id'] = self.lead_id.user_id.id
                #payment_mode_id
                if self.external_source_id.external_sale_order_account_payment_mode_id.id>0:
                    sale_order_vals['payment_mode_id'] = self.external_source_id.external_sale_order_account_payment_mode_id.id
                #payment_term_id
                if self.external_source_id.external_sale_order_account_payment_term_id.id>0:
                    sale_order_vals['payment_term_id'] = self.external_source_id.external_sale_order_account_payment_term_id.id                            
                #create
                sale_order_obj = self.env['sale.order'].sudo(self.create_uid).create(sale_order_vals)
                #define
                self.sale_order_id = sale_order_obj.id
                #external_sale_order_shipping_id
                for external_sale_order_shipping_id in self.external_sale_order_shipping_ids:                    
                    #data
                    data_sale_order_line = {
                        'order_id': self.sale_order_id.id,
                        'product_id': self.external_source_id.external_sale_order_shipping_product_template_id.id,
                        'name': str(external_sale_order_shipping_id.title),                    
                        'product_uom_qty': 1,
                        'product_uom': 1,
                        'price_unit': external_sale_order_shipping_id.unit_price_without_tax,
                        'discount': 0
                    }
                    #Fix product_uom
                    if self.external_source_id.external_sale_order_shipping_product_template_id.uom_id.id>0:
                        data_sale_order_line['product_uom'] = self.external_source_id.external_sale_order_shipping_product_template_id.uom_id.id
                    #create
                    sale_order_line_obj = self.env['sale.order.line'].sudo(self.create_uid).create(data_sale_order_line)
                    #update
                    external_sale_order_shipping_id.sale_order_line_id = sale_order_line_obj.id                
                #lines
                for external_sale_order_line_id in self.external_sale_order_line_ids:
                    #data
                    data_sale_order_line = {
                        'order_id': self.sale_order_id.id,
                        'product_id': external_sale_order_line_id.external_product_id.product_template_id.id,
                        'name': str(external_sale_order_line_id.title),
                        'product_uom_qty': external_sale_order_line_id.quantity,
                        'product_uom': 1,
                        'price_unit': external_sale_order_line_id.unit_price_without_tax,
                        'discount': 0                
                    } 
                    #Fix product_uom
                    if external_sale_order_line_id.external_product_id.product_template_id.uom_id.id>0:
                        data_sale_order_line['product_uom'] = external_sale_order_line_id.external_product_id.product_template_id.uom_id.id
                    #create                
                    sale_order_line_obj = self.env['sale.order.line'].sudo(self.create_uid).create(data_sale_order_line)
                    #update
                    external_sale_order_line_id.sale_order_line_id = sale_order_line_obj.id                                                                                             
        #return
        return False
    
    @api.one
    def action_sale_order_done_error_partner_id_without_vat(self):
        _logger.info('No se puede confirmar el pedido '+str(self.sale_order_id.name)+' porque el cliente NO tiene CIF')
                            
    @api.one
    def action_sale_order_done(self):
        if self.sale_order_id.id>0:
            if self.sale_order_id.state in ['draft', 'sent']:
                if self.sale_order_id.partner_id.vat==False:
                    self.action_sale_order_done_error_partner_id_without_vat()
                else:
                    self.sale_order_id.sudo(self.create_uid).action_confirm()
            
    @api.multi
    def action_payment_transaction_create_multi(self):
        for obj in self:
            if obj.payment_transaction_id.id==0:
                obj.action_payment_transaction_create()
    
    @api.one
    def action_payment_transaction_create(self):
        if self.payment_transaction_id.id==0:
            if self.sale_order_id.id>0:
                if self.external_customer_id.id>0:
                    if self.external_customer_id.partner_id.id>0:
                        #payment_transaction
                        payment_transaction_vals = {
                            'reference': self.sale_order_id.name,
                            'sale_order_id': self.sale_order_id.id,
                            'amount': self.total_price,
                            'currency_id': self.currency_id.id,
                            'partner_id': self.external_customer_id.partner_id.id,
                            'acquirer_id': self.external_source_id.external_sale_payment_acquirer_id.id,
                            'date_validate': self.date,
                            'state': 'draft',
                        }
                        payment_transaction_obj = self.env['payment.transaction'].sudo(self.create_uid).create(payment_transaction_vals)
                        #write
                        payment_transaction_obj.write({
                            'state': 'done'
                        })
                        #update
                        self.payment_transaction_id = payment_transaction_obj.id            
    
    @api.one
    def action_crm_lead_win(self):
        if self.lead_id.id>0:
            if self.sale_order_id.state=='sale':
                if self.lead_id.probability<100:
                    self.lead_id.sudo(self.create_uid).action_set_won() 