# from odoo import http


# class MxSatCatalogs(http.Controller):
#     @http.route('/mx_sat_catalogs/mx_sat_catalogs', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mx_sat_catalogs/mx_sat_catalogs/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('mx_sat_catalogs.listing', {
#             'root': '/mx_sat_catalogs/mx_sat_catalogs',
#             'objects': http.request.env['mx_sat_catalogs.mx_sat_catalogs'].search([]),
#         })

#     @http.route('/mx_sat_catalogs/mx_sat_catalogs/objects/<model("mx_sat_catalogs.mx_sat_catalogs"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mx_sat_catalogs.object', {
#             'object': obj
#         })
