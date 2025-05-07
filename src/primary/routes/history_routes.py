from flask import Blueprint, request, jsonify, current_app
import logging

from src.primary.utils.hunting_manager import HuntingManager

logger = logging.getLogger("huntarr")
history_blueprint = Blueprint('history', __name__)

@history_blueprint.route('/<app_type>', methods=['GET'])
def get_app_history(app_type):
    """Get history entries for a specific app or all apps"""
    try:
        # Get the hunting manager instance from the Flask app
        hunting_manager = current_app.config['HUNTING_MANAGER']
        
        search_query = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        # Validate page_size to be one of the allowed values
        allowed_page_sizes = [10, 20, 30, 50, 100, 250, 1000]
        if page_size not in allowed_page_sizes:
            page_size = 20
        
        # Validate app_type
        valid_app_types = ["all", "sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros", "swaparr"]
        if app_type not in valid_app_types:
            return jsonify({"error": f"Invalid app type: {app_type}"}), 400
        
        # Handle 'all' app type specially
        if app_type == 'all':
            # Gather results from all app types and combine them
            all_results = {
                "total": 0,
                "page": page,
                "page_size": page_size,
                "items": []
            }
            
            for single_app_type in valid_app_types:
                if single_app_type != 'all':
                    result = hunting_manager.get_history(single_app_type, None, page, page_size)
                    if result and 'items' in result:
                        all_results["items"].extend(result["items"])
                        all_results["total"] += result["total"]
            
            # Sort by date_time (newest first)
            all_results["items"].sort(key=lambda x: x.get("date_time", 0), reverse=True)
            
            # Only take the first page_size items
            all_results["items"] = all_results["items"][:page_size]
            all_results["total_pages"] = (all_results["total"] + page_size - 1) // page_size
            
            result = all_results
        else:
            # Get history for specific app type
            result = hunting_manager.get_history(app_type, None, page, page_size)
            
        # For backward compatibility with frontend - rename 'items' to 'entries'
        if 'items' in result:
            result['entries'] = result['items']
            del result['items']
        
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error getting history for {app_type}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@history_blueprint.route('/<app_type>', methods=['DELETE'])
def clear_app_history(app_type):
    """Clear history for a specific app or all apps"""
    try:
        # Get the hunting manager instance from the Flask app
        hunting_manager = current_app.config['HUNTING_MANAGER']
        
        # Validate app_type
        valid_app_types = ["all", "sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros", "swaparr"]
        if app_type not in valid_app_types:
            return jsonify({"error": f"Invalid app type: {app_type}"}), 400
        
        if app_type == 'all':
            success = hunting_manager.clear_history()
        else:
            success = hunting_manager.clear_history(app_type)
            
        if success:
            return jsonify({"message": f"History cleared for {app_type}"}), 200
        else:
            return jsonify({"error": f"Failed to clear history for {app_type}"}), 500
    
    except Exception as e:
        logger.error(f"Error clearing history for {app_type}: {str(e)}")
        return jsonify({"error": str(e)}), 500
