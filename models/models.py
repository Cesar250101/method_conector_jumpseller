# -*- coding: utf-8 -*-

from odoo import models, fields, api
import requests
import math
import pandas as pd
import flatten_json  
import datetime


class Company(models.Model):
    _inherit = 'res.company'

    jumpseller_login=fields.Char(string="Longin JumpSeller")
    jumpseller_authtoken=fields.Char(string="Auth Token JumpSeller")



class NotasVenta(models.Model):
    _inherit = 'sale.order'
    
    jumpseller_payment_method_name=fields.Char(string='Pago JumpSeller')
    jumpseller_status_order=fields.Char(string='Status JumpSeller')
    jumpseller_duplicate_url=fields.Char(string='URL Pedido Jumpseller')
    jumpseller_order_id=fields.Integer(string='Id Order Jumpseller')
    

    @api.model
    def sync_sale_order_jumpseller(self):
        login=self.env.user.company_id.jumpseller_login
        authtoken=self.env.user.company_id.jumpseller_authtoken
        url_api_orders_contar = "https://api.jumpseller.com/v1/orders/count.json"
        url_api_orders = "https://api.jumpseller.com/v1/orders.json"
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
        print("Total de productos:", conteo_ordes)

        productos_paginas = math.ceil(conteo_ordes / 100)  # 100 productos por página, seleccionado en parámetro limit
        print("Total de páginas:", productos_paginas)

        # obtener los json con los datos de los productos

        json_datos_completo = []  # lista para almacenar todos los json a descargar con requests

        for pagina_actual in range(1, productos_paginas + 1):

            parametros_orders["page"] = str(pagina_actual)
            respuesta = requests.get(url_api_orders, headers=header_api, params=parametros_orders)
            json_datos = respuesta.json()
            json_datos_completo += json_datos
            print("Leyendo página", pagina_actual, "...")
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
                duplicate_url=pw['order']['duplicate_url']
                customer=pw['order']['customer']['id']
                shipping_address= pw['order']['shipping_address']['address']+" "+pw['order']['shipping_address']['municipality']
                billing_address=pw['order']['billing_address']['address']+" "+pw['order']['billing_address']['municipality']
                    
                partner_id=self.env['res.partner'].search([('jumpseller_custom_id', '=', customer)],limit=1)
                direccion_despacho=self.env['res.partner'].search([('street', '=', shipping_address)],limit=1)
                direccion_facturacion=self.env['res.partner'].search([('street', '=', shipping_address)],limit=1)
                order_all=self.env['sale.order'].search([('jumpseller_order_id', '=', order_id)],limit=1)
                productos=pw['order']['products']
                
                if direccion_facturacion:
                    df=direccion_facturacion.id
                else:
                    df=partner_id.id
                        
                if direccion_despacho:
                    dd=direccion_despacho.id
                else:
                    dd=partner_id.id

                if order_date:
                    do=order_date
                else:
                    do=datetime.datetime.now()
                        
                    
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
                                "partner_shipping_id":dd,
                                "partner_invoice_id":df,
                                "jumpseller_status_order":status,
                            }
                if order_all:
                    id_order=self.write(values)
                    id_order=self.search([('jumpseller_order_id','=',order_id)],limit=1)
                else:
                    id_order= self.create(values)
                
                for p in productos:
                    producto_id=p['id']                        
                    producto_sku=p['sku']                        
                    producto_cantidad=p['qty']
                    producto_precio=p['price']
                    producto_dscto=p['discount']
                    producto_dscto=(producto_dscto/producto_precio)*100
                        
                    id_producto=self.env['product.template'].search([('jumpseller_product_id','=',producto_id)],limit=1).id                        
                    producto_uom=self.env['product.template'].search([('jumpseller_product_id','=',producto_id)],limit=1).uom_id                        
                    product_product_id=self.env['product.product'].search([('product_tmpl_id','=',id_producto)],limit=1).id                        
                        
                    values = {
                                "product_id": product_product_id,
                                "product_uom_qty":producto_cantidad,
                                "price_unit": producto_precio,
                                "discount": producto_dscto,
                                "order_id":id_order.id,
                                "product_uom":producto_uom.id,
                            }
                    linea_detalle=self.env['sale.order.line'].search([('product_id','=',product_product_id)])
                    if linea_detalle:
                        id_linea=linea_detalle.write(values)
                    else:
                        id_linea=linea_detalle.create(values)
                        

class Clientes(models.Model):
    _inherit = 'res.partner'
    
    jumpseller_custom_id=fields.Char(string="Id Cliente JumpSeller")

    @api.model
    def sync_customer_jumpseller(self):
        login=self.env.user.company_id.jumpseller_login
        authtoken=self.env.user.company_id.jumpseller_authtoken
        url_api_clientes_contar = "https://api.jumpseller.com/v1/customers/count.json"
        url_api_clientes = "https://api.jumpseller.com/v1/customers.json"
        header_api = {'Content-Type': 'application/json'}
        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_contar = {"login": login,
                            "authtoken": authtoken}

        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_clientes = {"login": login,
                                "authtoken": authtoken,
                                "limit": "100",
                                "page": "1"}


        # +++++ comienzo +++++

        # obtener la cantidad total de productos y calcular el número de páginas a consultar con requests

        respuesta_contar = requests.get(url_api_clientes_contar, headers=header_api, params=parametros_contar)
        conteo_productos = respuesta_contar.json()["count"]
        print("Total de productos:", conteo_productos)

        productos_paginas = math.ceil(conteo_productos / 100)  # 100 productos por página, seleccionado en parámetro limit
        print("Total de páginas:", productos_paginas)

        # obtener los json con los datos de los productos

        json_datos_completo = []  # lista para almacenar todos los json a descargar con requests

        for pagina_actual in range(1, productos_paginas + 1):

            parametros_clientes["page"] = str(pagina_actual)
            respuesta = requests.get(url_api_clientes, headers=header_api, params=parametros_clientes)
            json_datos = respuesta.json()
            json_datos_completo += json_datos
            print("Leyendo página", pagina_actual, "...")
            for pw in json_datos_completo:
                custom_id=pw['customer']['id']
                email=pw['customer']['email']
                phone=pw['customer']['phone']
                address=""
                
                values = {
                                "name": 'Paso',
                                #"street":address,
                                "email": email,
                                "mobile": phone,
                                #"city_id":municipality,
                                #"city":city,
                                "type":'contact',   
                                "jumpseller_custom_id":custom_id,
                            }
                clientes_1=self.env['res.partner'].search([('email', '=', email),('type','=','contact')],limit=1)
                if clientes_1:
                    parent_id=self.write(values)
                else:
                    parent_id=self.create(values)
                if parent_id and parent_id != True:
                    direccion_facturacion=pw['customer']['billing_addresses']                
                    i=1
                    for c in direccion_facturacion:
                        name=c['name']+" "+c['surname']               
                        city=c['city']
                        municipality=c['municipality']
                        address=c['address'] +" "+c['municipality']                    
                        type="invoice"
                        values = {
                                    "name": name,
                                    "street":address,
                                    "email": email,
                                    "mobile": phone,
                                    #"city_id":municipality,
                                    "city":city,
                                    "type":type,   
                                    "jumpseller_custom_id":custom_id,
                                    "parent_id":parent_id.id,
                                }
                        clientes_all=self.env['res.partner'].search([('street', '=', address)],limit=1)
                        if clientes_all:                        
                            cliente_id=self.write(values)   
                        else:
                            cliente_id=self.create(values)  
                        if i==1:
                            parent=self.env['res.partner'].search([('id','=',parent_id.id)],limit=1)                     
                            values = {
                                        "name": name,
                                        "street":address,
                                        #"city_id":municipality,
                                        "city":city,
                                    }                        
                            parent.write(values)
                        i+=1
                    direccion_envio=pw['customer']['shipping_addresses']
                    for c in direccion_envio:
                        name=c['name']+" "+c['surname']               
                        city=c['city']
                        municipality=c['municipality']
                        address=c['address']+" "+c['municipality']
                        type="delivery"
                        clientes_all=self.env['res.partner'].search([('street', '=', address),('type','=','delivery')],limit=1)
                        values = {
                                    "name": name,
                                    "street":address,
                                    "email": email,
                                    "mobile": phone,
                                    #"city_id":municipality,
                                    "city":city,
                                    "type":type,
                                    "jumpseller_custom_id":custom_id,
                                    "parent_id":cliente_id,
                                    "parent_id":parent_id.id,
                                }

                        if clientes_all:                            
                            cliente_id=self.write(values)   
                        else:
                            cliente_id=self.create(values)  

class Productos(models.Model):
    _inherit = 'product.template'

    jumpseller_sku=fields.Char(string="SKU JumpSeller")
    jumpseller_product_id=fields.Char(string="ID Producto JumpSeller")
    jumpseller_categ=fields.Char(string="Categoria JumpSeller")
    jumpseller_img=fields.Char(string="Imagen Producto JumpSeller")

    
    @api.model
    def sync_poroduct_jumpseller(self):
        login=self.env.user.company_id.jumpseller_login
        authtoken=self.env.user.company_id.jumpseller_authtoken
        url_api_productos_contar = "https://api.jumpseller.com/v1/products/count.json"
        url_api_productos = "https://api.jumpseller.com/v1/products.json"
        header_api = {'Content-Type': 'application/json'}
        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_contar = {"login": login,
                            "authtoken": authtoken}

        # completar con los parámetros API de acceso a la tienda Jumpseller
        parametros_productos = {"login": login,
                                "authtoken": authtoken,
                                "limit": "100",
                                "page": "1"}

        respuesta_contar = requests.get(url_api_productos_contar, headers=header_api, params=parametros_contar)
        conteo_productos = respuesta_contar.json()["count"]
        print("Total de productos:", conteo_productos)

        productos_paginas = math.ceil(conteo_productos / 100)  # 100 productos por página, seleccionado en parámetro limit
        print("Total de páginas:", productos_paginas)

        # obtener los json con los datos de los productos

        json_datos_completo = []  # lista para almacenar todos los json a descargar con requests

        for pagina_actual in range(1, productos_paginas + 1):

            parametros_productos["page"] = str(pagina_actual)
            respuesta = requests.get(url_api_productos, headers=header_api, params=parametros_productos)
            json_datos = respuesta.json()
            json_datos_completo += json_datos
            print("Leyendo página", pagina_actual, "...")
        for pw in json_datos_completo:                
            sku=pw['product']['sku']
            id=pw['product']['id']
            name=pw['product']['name']
            descripton_sale=pw['product']['meta_description']
            list_price=pw['product']['price']
            categoria=pw['product']['categories']
            categ=""
            for c in categoria:
                categ+=c['name'] +'/'

            imagen=pw['product']['images']
            for i in imagen:
                img=i['url']
            type="product"
            if sku:
                productos_all=self.env['product.template'].search([('default_code', '=', sku)],limit=1)
            else:
                productos_all=self.env['product.template'].search([('name', '=', name)],limit=1)
            values = {
                            "default_code": sku,
                            "jumpseller_sku":sku,
                            "jumpseller_product_id":id,
                            "name": name,
                            "lst_price": list_price,
                            "descripton_sale":descripton_sale,
                            "type":type,
                            "available_in_pos":True,
                            'jumpseller_categ':categ,
                            'jumpseller_img':img,
                            
                        }
            if productos_all:
                product_id=self.write(values)   
            else:
                product_id=self.create(values)   
