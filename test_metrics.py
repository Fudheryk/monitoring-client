import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from monitoring_client.collectors.loader import run_builtin_collectors

print("=== Test des nouvelles métriques ===")
metrics = run_builtin_collectors()

# Compter le total
print(f"Total des métriques : {len(metrics)}")

# Afficher les nouvelles métriques
new_metrics = []
for m in metrics:
    name = m['name']
    if 'cpu.count' in name or 'disk[' in name or 'temperature.' in name:
        new_metrics.append(m)
        
print(f"\n=== Nouvelles métriques ({len(new_metrics)} trouvées) ===")
for m in new_metrics:
    print(f"{m['name']}: {m['value']} ({m['type']})")

# Afficher aussi quelques autres pour vérifier
print(f"\n=== Quelques autres métriques système ===")
system_metrics = [m for m in metrics if m['name'].startswith(('system.', 'memory.', 'swap.', 'cpu.'))]
for m in system_metrics[:10]:
    print(f"{m['name']}: {m['value']}")
