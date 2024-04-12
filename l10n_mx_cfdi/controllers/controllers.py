# from odoo import http


# class InvoiceMxCfdi(http.Controller):
#     @http.route('/l10n_mx_cfdi/l10n_mx_cfdi', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/l10n_mx_cfdi/l10n_mx_cfdi/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('l10n_mx_cfdi.listing', {
#             'root': '/l10n_mx_cfdi/l10n_mx_cfdi',
#             'objects': http.request.env['l10n_mx_cfdi.l10n_mx_cfdi'].search([]),
#         })

#     @http.route('/l10n_mx_cfdi/l10n_mx_cfdi/objects/<model("l10n_mx_cfdi.l10n_mx_cfdi"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('l10n_mx_cfdi.object', {
#             'object': obj
#         })
