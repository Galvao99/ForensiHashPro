from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from web.backend.app.database import SessionFactory
from web.backend.app.models import User, UserPrivacyPreferences, UserRole
from web.backend.app.security import hash_password, normalize_email, validate_password


def create_admin(
    session_factory: sessionmaker[Session],
    *,
    name: str,
    email: str,
    password: str,
) -> User:
    normalized_name = name.strip()
    if not 2 <= len(normalized_name) <= 160:
        raise ValueError("O nome deve possuir entre 2 e 160 caracteres.")
    normalized_email = normalize_email(email)
    validate_password(password)
    with session_factory() as database:
        if database.scalar(select(User).where(User.email == normalized_email)):
            raise ValueError("Já existe uma conta com este e-mail.")
        admin = User(
            name=normalized_name,
            email=normalized_email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            privacy=UserPrivacyPreferences(),
        )
        database.add(admin)
        try:
            database.commit()
        except IntegrityError as error:
            database.rollback()
            raise ValueError("Já existe uma conta com este e-mail.") from error
        database.refresh(admin)
        return admin


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: sessionmaker[Session] = SessionFactory,
    input_reader: Callable[[str], str] = input,
    password_reader: Callable[[str], str] = getpass.getpass,
) -> int:
    parser = argparse.ArgumentParser(description="Administração local do ForensiHash Web.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-admin", help="Cria explicitamente uma conta ADMIN.")
    create.add_argument("--name")
    create.add_argument("--email")
    arguments = parser.parse_args(argv)

    if arguments.command == "create-admin":
        name = arguments.name or input_reader("Nome: ")
        email = arguments.email or input_reader("E-mail: ")
        password = password_reader("Senha: ")
        confirmation = password_reader("Confirme a senha: ")
        if password != confirmation:
            print("As senhas não coincidem.", file=sys.stderr)
            return 1
        try:
            admin = create_admin(
                session_factory,
                name=name,
                email=email,
                password=password,
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"Conta ADMIN criada para {admin.email}.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
