from food_safety.cli import main

if __name__ == "__main__":
    import sys

    sys.argv.insert(1, "update")
    main()
