from app.core.database import SessionLocal
from app.services.analytics_service import get_dashboard_stats_service
import json

def verify_fix():
    db = SessionLocal()
    try:
        stats = get_dashboard_stats_service(db)
        print("\n--- Analytics Verification ---")
        print(f"Total INR Spend: {stats['costs']['total_inr']}")
        print(f"Total USD Spend: {stats['costs']['total_usd']:.2f}")
        
        if stats['costs']['total_inr'] > 0:
            print("\n[SUCCESS] Total spend is now correctly displaying non-zero values.")
        else:
            print("\n[WARNING] Total spend is still zero. Check if there is data in whatsapp_messages.whatsapp_cost.")
    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_fix()
