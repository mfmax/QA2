#!/usr/bin/env python3
import subprocess
import sys

def run_command(command):
    """Выполняет команду в терминале и выводит результат."""
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        print(result.stdout)
        if result.stderr:
            print("Предупреждение:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении команды: {' '.join(command)}")
        print("Сообщение об ошибке:", e.stderr)
        sys.exit(1)

def main():
    # Запрашиваем комментарий
    message = input("Введите комментарий для коммита: ").strip()
    
    if not message:
        print("Комментарий не может быть пустым!")
        sys.exit(1)

    print("\nВыполняю: git add .")
    run_command("git add .")

    print(f"\nВыполняю: git commit -m \"{message}\"")
    run_command(f'git commit -m "{message}"')

    print("\nВыполняю: git push")
    run_command("git push")

    print("\n✅ Успешно отправлено на GitHub!")

if __name__ == "__main__":
    main()