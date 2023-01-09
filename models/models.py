# -*- coding: utf-8 -*-

import base64
from odoo.tools.float_utils import float_split_str
from odoo.tools import convert
from odoo import models, fields, api
import requests
import math
import pandas as pd
import flatten_json  
import datetime
import json
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools import image
    


class Factura(models.Model):
    _inherit = 'account.invoice'
    
    ordenes_ids = fields.Many2many(comodel_name='sale.order', string='Notas de Venta')
    
    
    @api.multi
    def action_invoice_open(self):
        factura = super(Factura, self).action_invoice_open()
        for i in self.ordenes_ids:
            i.sudo().write({
                'invoice_status':'invoiced',
                'invoice_ids': [(4,self.id,False)],
            })
            #i._get_invoiced()            
            
        
    
    

class Company(models.Model):
    _inherit = 'res.company'

    jumpseller_login=fields.Char(string="Longin JumpSeller")
    jumpseller_authtoken=fields.Char(string="Auth Token JumpSeller")
    jumpseller_location_id = fields.Many2one(comodel_name='stock.location', string='Ubicación Para Descuento', domain="[('usage', '=', 'internal')]")    
    facturacion = fields.Boolean('Factura Automática?')



class PagosJumpSeller(models.Model):
    _name = 'method_conector_jumpseller.metodopago'

    name = fields.Char(string='Name')
    journal_id = fields.Many2one(comodel_name='account.journal', string='Diario Pago')
    
    
    
    


class JournalPagosJumpSeller(models.Model):
    _inherit = 'account.journal'

    jumpseller_metodo_pago = fields.Many2one(comodel_name='method_conector_jumpseller.metodopago', string='Method Pago JumpSeller')
    jumpseller_metodo_pago_ids = fields.One2many(comodel_name='method_conector_jumpseller.metodopago',
                                                 inverse_name='journal_id', string='Diario de Pago')
    
    jumpseller_facturar_terceros = fields.Boolean(string='Facturar a Terceros')
    jumpseller_tipo_factura = fields.Many2one(comodel_name='account.journal.sii_document_class', string='Tipo Documento')
    
        


class NotasVenta(models.Model):
    _inherit = 'sale.order'
    
    jumpseller_payment_method_name=fields.Char(string='Pago JumpSeller')
    jumpseller_status_order=fields.Char(string='Status JumpSeller')
    jumpseller_duplicate_url=fields.Char(string='URL Pedido Jumpseller')
    jumpseller_order_id=fields.Integer(string='Id Order Jumpseller')
    

    @api.model
    def cron_cambia_status_facturacion(self):
        para_factuar=self.env['sale.order'].search([('invoice_status','=','to invoice')])
        for i in para_factuar:
            factura=self.env['account.invoice'].search([('origin','=',i.name)])
            if factura:
                i.invoice_status='invoiced'

    @api.model
    def sync_sale_order_jumpseller(self):
        last_id = self.env['sale.order'].search([('jumpseller_order_id','!=',False)],order="jumpseller_order_id desc", limit=1).jumpseller_order_id
        #https://api.jumpseller.com/v1/orders/after/{id}.json
        login=self.env.user.company_id.jumpseller_login
        factura_automatica=self.env.user.company_id.facturacion
        authtoken=self.env.user.company_id.jumpseller_authtoken
        url_api_orders_contar = "https://api.jumpseller.com/v1/orders/count.json"
        url_api_orders = "https://api.jumpseller.com/v1/orders/after/"+ str(last_id) +".json"
        header_api = {'Content-Type': 'application/json'}
        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_contar = {"login": login,
                            "authtoken": authtoken}

        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_orders = {"login": login,
                                "authtoken": authtoken,
                                "limit": "100",
                                "page": "1"}

        respuesta_contar = requests.get(url_api_orders_contar, headers=header_api, params=parametros_contar)
        conteo_ordes = respuesta_contar.json()["count"]

        productos_paginas = math.ceil(conteo_ordes / 100)  # 100 productos por página, seleccionado en parámetro limit

        # obtener los json con los datos de los productos

        json_datos_completo = []  # lista para almacenar todos los json a descargar con requests

        for pagina_actual in range(1, productos_paginas + 1):
            parametros_orders["page"] = str(pagina_actual)
            respuesta = requests.get(url_api_orders, headers=header_api, params=parametros_orders)
            json_datos = respuesta.json()
            json_datos_completo += json_datos

        # respuesta = requests.get(url_api_orders, headers=header_api, params=parametros_orders)
        # json_datos = respuesta.json()
        # json_datos_completo += json_datos


        
        for pw in json_datos_completo:                 
            status=pw['order']['status']
                
            if status=="Paid":
                
                order_id=pw['order']['id']
                order_date=pw['order']['completed_at']
                order_subtotal=pw['order']['subtotal']
                order_tax=pw['order']['tax']
                order_total=pw['order']['total']
                order_discount=pw['order']['discount']
                payment_method_type=pw['order']['payment_method_type']
                payment_method_name=pw['order']['payment_method_name']
                
                payment_method_id=self.env['method_conector_jumpseller.metodopago'].search([('name','=',payment_method_name)],limit=1)
                if payment_method_id.id ==False:
                    values={
                            'name':payment_method_name,
                        }
                    payment_method_id=payment_method_id.create(values)
                #Buscar journal
                journal_id=self.env['account.journal'].search([('jumpseller_metodo_pago_ids','=',payment_method_id.id)],limit=1)
                tipodocto_factura=journal_id.jumpseller_tipo_factura
                documento_boleta=self.env['sii.document_class'].search([('sii_code','=','39')],limit=1).id
                documento_factura=self.env['sii.document_class'].search([('sii_code','=','33')],limit=1).id

                
                #document_class_boleta=self.env['account.journal.sii_document_class'].search([('sii_document_class_id','=',documento_boleta)],limit=1).id
                #document_class_factura=self.env['account.journal.sii_document_class'].search([('sii_document_class_id','=',documento_factura)],limit=1).id
                
                tipodocto_jumpseller=pw['order']['additional_fields']
                for t in tipodocto_jumpseller:
                    if t['label']=='Boleta o Factura':
                        if t['value']=='Boleta':
                            tipodocto_method=documento_boleta
                            document_class_id=self.env['account.journal.sii_document_class'].search([('sii_document_class_id','=',documento_boleta)],limit=1).id
                        elif t['value']=='Factura':
                            tipodocto_method=documento_factura
                            document_class_id=self.env['account.journal.sii_document_class'].search([('sii_document_class_id','=',documento_factura)],limit=1).id
                        eligio_documento=t['value']
                duplicate_url=pw['order']['duplicate_url']
                customer=pw['order']['customer']['id']
                if pw['order']['shipping_address']!=None:
                    shipping_address= pw['order']['shipping_address']['address']+" "+pw['order']['shipping_address']['municipality']
                    billing_address=pw['order']['billing_address']['address']+" "+pw['order']['billing_address']['municipality']
                else:
                    shipping_address=""
                    billing_address=""

                partner_id=self.env['res.partner'].search([('jumpseller_custom_id', '=', customer)],limit=1)
                direccion_despacho=self.env['res.partner'].search([('street', '=', shipping_address)],limit=1)
                direccion_facturacion=self.env['res.partner'].search([('street', '=', shipping_address)],limit=1)
                order_all=self.env['sale.order'].search([('jumpseller_order_id', '=', order_id)],limit=1)
                productos=pw['order']['products']
                
                if partner_id.id==False:
                    email=pw['order']['customer']['email']
                    telefono= pw['order']['customer']['phone']
                    if eligio_documento=="Boleta":
                        nombre=pw['order']['billing_address']['name']+" "+pw['order']['billing_address']['surname']
                        rut=""
                    else:
                        nombre=pw['order']['billing_address']['name']
                        rut=pw['order']['billing_address']['taxid']
                    direccion=pw['order']['billing_address']['address']
                    ciudad=pw['order']['billing_address']['city']
                    comuna=pw['order']['billing_address']['municipality']
                    comuna_id=self.env['res.city'].search([('name','=',comuna)],limit=1)
                    if comuna_id.id ==False:
                        values={
                            'name':comuna,
                            'country_id':46,
                            'code':'CL27900'
                        }
                        comuna_id=self.env['res.city'].create(values)
                    values = {
                                "document_number":rut,
                                "name":nombre,
                                "email": email,
                                "mobile":telefono,
                                "street": direccion,
                                "city": ciudad,
                                "city_id":comuna_id.id,
                                'type':'contact',
                                'jumpseller_custom_id':customer,
                            }
                    partner_id=partner_id.create(values)
                
                    if direccion_facturacion.id==False:
                        values = {
                                    "document_number":rut,
                                    "name":nombre,
                                    "email": email,
                                    "mobile":telefono,
                                    "street": direccion,
                                    "city": ciudad,
                                    "city_id":comuna_id.id,
                                    'type':'invoice',
                                    'parent_id':partner_id.id
                                }
                        direccion_facturacion=self.env['res.partner'].create(values)
                    if direccion_despacho.id==False:
                        values = {
                                    
                                    "name":nombre,
                                    "email": email,
                                    "mobile":telefono,
                                    "street": direccion,
                                    "city": ciudad,
                                    "city_id":comuna_id.id,
                                    'type':'delivery',
                                    'parent_id':partner_id.id
                                }
                        direccion_despacho=self.env['res.partner'].create(values)
                                    
                if order_date:
                    do=order_date
                else:
                    do=datetime.datetime.now()
                                            
                order_line=[]                
                order_line_invoice=[]
                for p in productos:                    
                    if p['variant_id']==None:
                        jumpseller_producto_id=p['id']                        
                    else:
                        jumpseller_producto_id=p['variant_id']                        
                    producto_sku=p['sku']                        
                    producto_cantidad=p['qty']
                    producto_precio=p['price']
                    producto_dscto=p['discount']
                    producto_dscto=(producto_dscto/producto_precio)*100
                        
                    id_producto=self.env['product.template'].search([('jumpseller_product_id','=',jumpseller_producto_id)],limit=1).id
                    product=self.env['product.template'].search([('jumpseller_product_id','=',jumpseller_producto_id)],limit=1)
                    if product:
                        product_account_id=product.property_account_expense_id.id
                        if product_account_id==False:
                            product_account_id=product.categ_id.property_account_expense_categ_id.id
                        
                    producto_uom=self.env['product.template'].search([('jumpseller_product_id','=',jumpseller_producto_id)],limit=1).uom_id                        
                    product_product_id=self.env['product.product'].search([('product_tmpl_id','=',id_producto)],limit=1)                      
                    

                    order_line.append(
                            (0, 0, {
                                "product_id": product_product_id.id,
                                "product_uom_qty":producto_cantidad,
                                "price_unit": producto_precio,
                                "discount": producto_dscto,
                                #"order_id":id_order.id,
                                "product_uom":producto_uom.id,
                                "name":product_product_id.product_tmpl_id.name,   
                            }))

                    order_line_invoice.append(
                            (0, 0, {
                                "product_id": product_product_id.id,
                                "quantity":producto_cantidad,
                                "price_unit": producto_precio,
                                "discount": producto_dscto,
                                #"order_id":id_order.id,
                                "uom_id":producto_uom.id,
                                "unmdItem":producto_uom.id,
                                "name":product_product_id.product_tmpl_id.name,   
                                "account_id":product_account_id,
                            }))

                

                values = {
                                "name":order_id,
                                "jumpseller_order_id": order_id,
                                "date_order":do,
                                "amount_untaxed": order_subtotal,
                                "amount_tax": order_tax,
                                "amount_total":order_total,
                                "jumpseller_payment_method_name":payment_method_name,
                                "jumpseller_duplicate_url":duplicate_url,
                                "partner_id":partner_id.id,
                                #"partner_shipping_id":direccion_despacho.id,
                                "partner_shipping_id":partner_id.id,
                                #"partner_invoice_id":direccion_facturacion.id,
                                "partner_invoice_id":partner_id.id,
                                "jumpseller_status_order":status,
                                "order_line":order_line,
                            }
                
                if order_all.id==False:
                    id_order= self.create(values)
                    id_order.action_confirm()
                    if factura_automatica:
                        if journal_id.jumpseller_facturar_terceros==False:
                            if tipodocto_factura.id!=False:
                                values['journal_document_class_id'] = document_class_id
                                values['document_class_id'] = tipodocto_method
                                values['journal_id'] = 1
                                values['origin'] = id_order.name
                                values['name'] = id_order.id
                                values['invoice_line_ids'] = order_line_invoice
                                
                                factura=self.env['account.invoice'].create(values)
                                if eligio_documento=="Boleta":
                                    factura.action_invoice_open()
                                
                                id_order.sudo().write({
                                    'invoice_status':'invoiced',
                                    'invoice_ids':(0, 0,  { factura.id }),
                                })
                    
                else:
                    id_order=self.search([('jumpseller_order_id','=',order_id)],limit=1)      

                

                


                        

class Clientes(models.Model):
    _inherit = 'res.partner'
    
    jumpseller_custom_id=fields.Char(string="Id Cliente JumpSeller")


class Productos(models.Model):
    _inherit = 'product.template'

    jumpseller_sku=fields.Char(string="SKU JumpSeller")
    jumpseller_product_id=fields.Integer(string="ID Producto JumpSeller")
    jumpseller_categ=fields.Char(string="Categoria JumpSeller")
    jumpseller_img=fields.Char(string="Imagen Producto JumpSeller")
    jumpseller_marca=fields.Char(string="Marca Producto")
    jumpseller_es_variante = fields.Boolean(string='Es Variante en JumpSeller')
    jumpseller_variente_id=fields.Integer(string="ID Variante JumpSeller")

    @api.model
    def sync_product_stock_method_jumpseller(self):
        login=self.env.user.company_id.jumpseller_login
        authtoken=self.env.user.company_id.jumpseller_authtoken
        header_api = {'Content-Type': 'application/json'}
        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_contar = {"login": login,
                            "authtoken": authtoken}

        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_products = {"login": login,
                                "authtoken": authtoken,
                                "limit": "100",
                                "page": "1"}        
        
        producto=self.env['product.template'].search([('jumpseller_product_id','!=',0)])
        for p in producto:
            product_id_js=str(p.jumpseller_product_id)  
            precio_venta=round((p.list_price*1.02),0)

            stock_ubicacion=self.env['stock.quant'].search([('product_tmpl_id','=',p.id),
                                                            ('location_id','=',self.env.user.company_id.jumpseller_location_id.id),
                                                            ('company_id','=',self.env.user.company_id.id)],limit=1)
            
            stock_diponible=stock_ubicacion.quantity-stock_ubicacion.reserved_quantity
            if stock_diponible<0:
                stock=0
            else:
                stock=stock_diponible
            product_sku_js=str(p.default_code)
            url_api_products_contar = "https://api.jumpseller.com/v1/products/" +str(product_id_js)+".json"
            # datadic={
            #     'product': {
            #     'stock': p.qty_available,
            #     }}
            datadic={
                        "product": {
                        "stock": stock,
                        "stock_unlimited": False,
                        "price": precio_venta,
                        }
                    }
        
            
            url = "https://api.jumpseller.com/v1/products/" +str(product_id_js)+".json"
            cabeceras_extra = { 
            'Accept': 'application/xml' 
            }
            respuesta = requests.put(url=url,data=json.dumps(datadic), headers=header_api,params=parametros_contar)

            

    
    @api.model
    def sync_product_jumpseller(self):
        login=self.env.user.company_id.jumpseller_login
        authtoken=self.env.user.company_id.jumpseller_authtoken
        url_api_products_contar = "https://api.jumpseller.com/v1/products/count.json"
        url_api_products = "https://api.jumpseller.com/v1/products.json"
        header_api = {'Content-Type': 'application/json'}
        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_contar = {"login": login,
                            "authtoken": authtoken}

        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_products = {"login": login,
                                "authtoken": authtoken,
                                "limit": "100",
                                "page": "1"}

        respuesta_contar = requests.get(url_api_products_contar, headers=header_api, params=parametros_contar)
        conteo_products = respuesta_contar.json()["count"]

        productos_paginas = math.ceil(conteo_products / 100)  # 100 productos por página, seleccionado en parámetro limit

        # obtener los json con los datos de los productos

        json_datos_completo = []  # lista para almacenar todos los json a descargar con requests

        for pagina_actual in range(1, productos_paginas + 1):
        # for pagina_actual in range(1, 4):
            parametros_products["page"] = str(pagina_actual)
            respuesta = requests.get(url_api_products, headers=header_api, params=parametros_products)
            json_datos = respuesta.json()
            json_datos_completo += json_datos
        for pw in json_datos_completo: 
            sku=pw['product']['sku']
            products_method=self.env['product.template'].search([('default_code','=',sku)],limit=1)
            if products_method.id==False:
                products_method=self.env['product.template'].search([('name','=',pw['product']['name'])],limit=1)
            categ=""
            imagen=""
            for c in pw['product']['categories']:
                categ+=c['name']+'/'
            for i in pw['product']['images']:
                try:
                    imagen=i['url']
                    imagen_base64 = base64.b64encode(requests.get(imagen.replace('\/', '/')).content)
                except:
                    imagen_base64=""
                    pass
            values={
                    'name':pw['product']['name'],
                    'image_medium':imagen_base64,
                    'default_code':pw['product']['sku'],
                    'jumpseller_sku':pw['product']['sku'],
                    'jumpseller_product_id':pw['product']['id'],
                    'jumpseller_categ':categ,
                    'jumpseller_img':imagen,
                    'list_price':pw['product']['price'],
                    'barcode':pw['product']['barcode'],
                    #'description_sale':pw['product']['description'],
                    'jumpseller_marca':pw['product']['brand'],   
                    'type':'product'                 
                }
            variants=pw['product']['variants']
            if not variants:
                if products_method.id==False:
                    product_id=products_method.create(values)
                else:
                    try:
                        product_id=products_method.write(values)
                    except:
                        del values['image_medium']
                        product_id=products_method.write(values)

                    products_method=self.env['product.template'].search([('jumpseller_sku','=',sku)],limit=1)
                    if products_method.id==False:
                        products_method=self.env['product.template'].search([('name','=',pw['product']['name'])],limit=1)
                
            #Variantes
            if variants:
                for v in variants:
                    opciones=v['options']
                    atributo=self.env['product.attribute'].search([('name','=',opciones[0]['name'])],limit=1)
                    if atributo.id==False:
                        values={
                                'name':opciones[0]['name'],
                                'create_variant':'always',
                                'type':'radio',
                                'jumpseller_id_atributo':opciones[0]['product_option_id']
                            }
                        atributo=self.env['product.attribute'].create(values)
                    atributo=self.env['product.attribute'].search([('name','=',opciones[0]['name'])],limit=1)
                    valor=opciones[0]['value']

                    producto_variante=self.env['product.template'].search([('jumpseller_variente_id','=',v['id'])])
                    values={
                                'name':pw['product']['name']+" "+valor ,
                                'image_medium':imagen_base64,
                                'default_code':v['sku'],
                                'jumpseller_sku':v['sku'],
                                'jumpseller_product_id':v['id'],
                                'jumpseller_categ':categ,
                                'jumpseller_img':imagen,
                                'list_price':v['price'],
                                #'description_sale':pw['product']['description'],
                                'jumpseller_marca':pw['product']['brand'],                    
                                'jumpseller_variente_id':v['id'],
                                'jumpseller_es_variante':True,
                                'image_medium':products_method.image_medium,
                                'image_small':products_method.image_small,
                            }
                    if producto_variante.id==False:
                        producto_variante.create(values)
                    else:
                        producto_variante.write(values)
