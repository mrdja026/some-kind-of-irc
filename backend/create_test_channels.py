from src.core.database import SessionLocal
from src.models.channel import Channel

def create_test_channels():
    # Create a new session
    db = SessionLocal()
    
    # Define channels to create
    channels_to_create = [
        {"name": "#ai", "type": "public"},
        {"name": "#lunch", "type": "public"},
        {"name": "#random", "type": "public"},
    ]
    
    created_count = 0
    existing_count = 0
    
    for channel_data in channels_to_create:
        # Check if channel already exists
        existing_channel = db.query(Channel).filter(Channel.name == channel_data["name"]).first()
        if existing_channel:
            print(f'Channel {channel_data["name"]} already exists (ID: {existing_channel.id})')
            existing_count += 1
            continue
        
        # Create a new channel
        new_channel = Channel(
            name=channel_data["name"],
            type=channel_data["type"]
        )
        
        # Add and commit the new channel
        db.add(new_channel)
        db.commit()
        db.refresh(new_channel)
        
        print(f'Channel {channel_data["name"]} created successfully. ID: {new_channel.id}')
        created_count += 1
    
    print(f'\nSummary: Created {created_count} channel(s), {existing_count} already existed.')
    db.close()

if __name__ == "__main__":
    create_test_channels()
