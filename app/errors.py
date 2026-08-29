from flask import jsonify

class APIError(Exception):
    def __init__(self, message, code="INVALID_REQUEST", status_code=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = jsonify({
            "status": "error",
            "error": {
                "code": error.code,
                "message": error.message
            }
        })
        response.status_code = error.status_code
        return response

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({
            "status": "error",
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found"
            }
        }), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        app.logger.error(f"Internal server error: {error}")
        return jsonify({
            "status": "error",
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal engine error occurred."
            }
        }), 500
