#!/usr/bin/env python3
"""
AegisGraph Neo4j Seed Script

Reads seed.cypher and executes all statements against the live Neo4j Aura instance.
Prints confirmation of nodes and relationships created.
"""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env from AegisGraph root directory
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    print("⚠️  Warning: python-dotenv not installed, relying on system environment variables")

# Add parent directory to path to import Neo4jClient
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.neo4j_client import Neo4jClient


async def seed_database():
    """Read seed.cypher and execute against Neo4j Aura instance."""
    # Read the seed.cypher file
    seed_file = Path(__file__).parent / "seed.cypher"
    
    if not seed_file.exists():
        print(f"❌ Error: seed.cypher not found at {seed_file}")
        sys.exit(1)
    
    print(f"📖 Reading seed data from {seed_file}")
    with open(seed_file, "r") as f:
        cypher_content = f.read()
    
    # Split into individual statements by looking for MERGE statements
    # Each MERGE block is a separate statement
    lines = cypher_content.split("\n")
    statements = []
    current_statement = []
    
    for line in lines:
        # Skip comments and empty lines
        if line.strip().startswith("//") or not line.strip():
            if current_statement:
                statements.append("\n".join(current_statement))
                current_statement = []
            continue
        current_statement.append(line)
    
    # Add the last statement if any
    if current_statement:
        statements.append("\n".join(current_statement))
    
    print(f"📝 Found {len(statements)} Cypher statements to execute\n")
    
    # Initialize Neo4j client
    try:
        client = Neo4jClient()
        print(f"✅ Connected to Neo4j at {os.environ.get('NEO4J_URI', 'N/A')}")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        sys.exit(1)
    
    # Execute each statement
    executed_count = 0
    try:
        for i, statement in enumerate(statements, 1):
            # Skip empty statements
            if not statement.strip():
                continue
            
            print(f"⚙️  Executing statement {i}/{len(statements)}...")
            try:
                result = await client.run_query(statement)
                executed_count += 1
                print(f"   ✓ Success")
            except Exception as e:
                print(f"   ⚠️  Warning: {e}")
        
        print(f"\n{'='*60}")
        print(f"✅ Seed script completed: {executed_count}/{len(statements)} statements executed")
        print(f"{'='*60}\n")
        
        # Verify the seeded data
        print("🔍 Verifying seeded data...\n")
        
        # Count doctors
        doctor_result = await client.run_query("MATCH (d:Doctor) RETURN count(d) as count")
        doctor_count = doctor_result[0]["count"] if doctor_result else 0
        print(f"   👨‍⚕️  Doctors: {doctor_count}")
        
        # Count patients
        patient_result = await client.run_query("MATCH (p:Patient) RETURN count(p) as count")
        patient_count = patient_result[0]["count"] if patient_result else 0
        print(f"   🏥 Patients: {patient_count}")
        
        # Count roles
        role_result = await client.run_query("MATCH (r:Role) RETURN count(r) as count")
        role_count = role_result[0]["count"] if role_result else 0
        print(f"   🎭 Roles: {role_count}")
        
        # Count TREATS relationships
        treats_result = await client.run_query("MATCH ()-[r:TREATS]->() RETURN count(r) as count")
        treats_count = treats_result[0]["count"] if treats_result else 0
        print(f"   🔗 TREATS relationships: {treats_count}")
        
        # Count HAS_ROLE relationships
        has_role_result = await client.run_query("MATCH ()-[r:HAS_ROLE]->() RETURN count(r) as count")
        has_role_count = has_role_result[0]["count"] if has_role_result else 0
        print(f"   🔗 HAS_ROLE relationships: {has_role_count}")
        
        print(f"\n{'='*60}")
        print("✅ Database seeding complete!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    # Check for required environment variables
    required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please set them in your .env file or environment")
        sys.exit(1)
    
    asyncio.run(seed_database())
