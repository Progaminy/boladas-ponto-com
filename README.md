# Boladas-ponto-com

**Do zero ao infinito.**

Boladas-ponto-com é um marketplace para vendedores particulares, lojas e empresas publicarem produtos e serviços em Moçambique.

## Publicação

O anúncio é criado com informação fornecida pelo próprio vendedor: título, descrição, categoria, preço, localização, contacto e 1 ou 2 fotografias reais do produto. O Boladas não cria automaticamente conteúdo para o anúncio.

## Funcionalidades

- feed público;
- diretório de lojas e empresas;
- comparação de preços e distância por GPS;
- perfis de utilizadores e empresas;
- até 2 fotos reais por produto;
- mensagens, comentários e reações;
- estados ativo, pausado e vendido;
- mediação humana opcional;
- denúncias e moderação humana;
- comprovativos PDF.

## Arquitetura

- FastAPI + Jinja2;
- PostgreSQL/Supabase em produção;
- SQLite apenas para desenvolvimento/testes quando `DATABASE_URL` não está definida;
- Backblaze B2 apenas para ficheiros: fotos, vídeos, fotos de perfil e capas.

## Configuração

Ver `.env.example`. Nunca coloques passwords ou chaves reais no repositório.

## Executar

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Saúde

- `/health` — aplicação;
- `/health/db` — banco;
- `/estado` — armazenamento B2.

## Nota sobre B2

Um erro 403 do Backblaze indica problema de bucket, região ou permissões da Application Key. Os dados estruturados continuam no banco; o B2 é necessário apenas para os ficheiros.
