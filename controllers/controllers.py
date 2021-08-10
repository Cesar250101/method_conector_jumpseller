# -*- coding: utf-8 -*-
from odoo import http

# class MethodConectorJumpseller(http.Controller):
#     @http.route('/method_conector_jumpseller/method_conector_jumpseller/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/method_conector_jumpseller/method_conector_jumpseller/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('method_conector_jumpseller.listing', {
#             'root': '/method_conector_jumpseller/method_conector_jumpseller',
#             'objects': http.request.env['method_conector_jumpseller.method_conector_jumpseller'].search([]),
#         })

#     @http.route('/method_conector_jumpseller/method_conector_jumpseller/objects/<model("method_conector_jumpseller.method_conector_jumpseller"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('method_conector_jumpseller.object', {
#             'object': obj
#         })