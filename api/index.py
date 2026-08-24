import os
import sys

# ✅ ESSA ERA A CAUSA RAIZ DE TUDO: esse arquivo (api/index.py) é o que
# a Vercel realmente executa (definido no vercel.json), mas ele tinha
# sua PRÓPRIA cópia do app FastAPI — separada e desatualizada em
# relação ao main.py. Toda vez que a gente atualizava main.py (novos
# routers, validação de login, CORS restrito), nada disso ia pro ar,
# porque a Vercel nunca rodava o main.py diretamente — só esse arquivo
# aqui, que ficou parado no tempo com só 4 routers e SEM proteção de
# login nenhuma.
#
# A correção: em vez de manter duas cópias do app (uma aqui, outra no
# main.py) que podem divergir de novo no futuro, esse arquivo agora só
# IMPORTA o app de verdade do main.py. Só existe uma fonte de verdade
# a partir de agora — qualquer mudança em main.py já vale pra produção
# automaticamente, sem precisar lembrar de duplicar em dois lugares.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from mangum import Mangum

handler = Mangum(app)