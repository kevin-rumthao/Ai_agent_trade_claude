import asyncio
import sys
import time
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.align import Align
from rich import box

from app.config import settings
from app.main import run_trading_loop

# Initialize Rich Console
console = Console()

class GameState:
    def __init__(self):
        self.level = 1
        self.xp = 0
        self.xp_to_next_level = 100
        self.total_profits = 0.0
        self.sessions_run = 0
        self.title = "Novice Trader"

    def add_xp(self, amount: int):
        self.xp += amount
        if self.xp >= self.xp_to_next_level:
            self.level_up()

    def level_up(self):
        self.level += 1
        self.xp -= self.xp_to_next_level
        self.xp_to_next_level = int(self.xp_to_next_level * 1.5)
        self.update_title()
        console.print(Panel(f"[bold green]LEVEL UP! You are now Level {self.level}![/bold green]", title="🎉 CONGRATULATIONS 🎉"))
        time.sleep(2)

    def update_title(self):
        if self.level < 5:
            self.title = "Novice Trader"
        elif self.level < 10:
            self.title = "Apprentice Chartist"
        elif self.level < 20:
            self.title = "Market Maker"
        else:
            self.title = "Whale"

game_state = GameState()

def print_header():
    console.clear()
    grid = Table.grid(expand=True)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right")
    
    title_text = Text("🤖 AI TRADING AGENT - COMMAND CENTER", style="bold cyan")
    stats_text = Text(f"Level {game_state.level} | {game_state.title} | XP: {game_state.xp}/{game_state.xp_to_next_level}", style="yellow")
    
    grid.add_row(title_text, stats_text)
    console.print(Panel(grid, style="blue"))

def show_main_menu():
    print_header()
    
    menu = Table(show_header=False, box=box.ROUNDED, expand=True)
    menu.add_column("Option", style="cyan", width=4)
    menu.add_column("Description", style="white")
    
    menu.add_row("1", "⚔️  Live Trading Arena [dim](Start the bot)[/dim]")
    menu.add_row("2", "🥋  Training Dojo [dim](Backtest/Simulate)[/dim]")
    menu.add_row("3", "🏆  Hall of Fame [dim](View Stats)[/dim]")
    menu.add_row("4", "⚙️  Armory [dim](Settings)[/dim]")
    menu.add_row("5", "🚪  Exit Game")
    
    console.print(menu)

async def run_live_trading():
    console.clear()
    console.print(Panel("[bold green]Entering the Live Trading Arena...[/bold green]", style="green"))
    console.print("Press Ctrl+C to retreat (stop trading).")
    time.sleep(1)
    
    try:
        # We need to run the async loop. Since we are already in an async function, 
        # but run_trading_loop is designed to be a top-level entry, we can just await it.
        # However, run_trading_loop handles its own loop.
        await run_trading_loop()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        console.print(f"[bold red]Error in the Arena: {e}[/bold red]")
    
    # Post-session gamification
    game_state.sessions_run += 1
    xp_gained = 50 # Base XP for running a session
    console.print(f"\n[bold yellow]+{xp_gained} XP for bravery![/bold yellow]")
    game_state.add_xp(xp_gained)
    
    Prompt.ask("\nPress Enter to return to base")

def show_backtest_menu():
    console.clear()
    console.print(Panel("[bold yellow]Training Dojo - Under Construction[/bold yellow]", style="yellow"))
    console.print("The simulation engine is being upgraded.")
    Prompt.ask("\nPress Enter to return")

def show_stats():
    console.clear()
    stats_table = Table(title="🏆 Hall of Fame 🏆", box=box.DOUBLE_EDGE)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Level", str(game_state.level))
    stats_table.add_row("Title", game_state.title)
    stats_table.add_row("Sessions Run", str(game_state.sessions_run))
    stats_table.add_row("Total Profits", f"${game_state.total_profits:.2f}")
    
    console.print(stats_table)
    Prompt.ask("\nPress Enter to return")

def show_settings():
    console.clear()
    settings_table = Table(title="⚙️ Armory (Configuration) ⚙️", box=box.SIMPLE)
    settings_table.add_column("Setting", style="magenta")
    settings_table.add_column("Value", style="yellow")
    
    # Display some key settings
    settings_table.add_row("Symbol", settings.symbol)
    settings_table.add_row("Provider", settings.trading_provider)
    settings_table.add_row("Interval", str(settings.loop_interval_seconds))
    settings_table.add_row("Max Position", str(settings.max_position_size))
    settings_table.add_row("Testnet", str(settings.testnet))
    
    console.print(settings_table)
    console.print("\n[dim]Edit .env file to change these values.[/dim]")
    Prompt.ask("\nPress Enter to return")

async def main_loop():
    while True:
        show_main_menu()
        choice = Prompt.ask("Choose your destiny", choices=["1", "2", "3", "4", "5"], default="1")
        
        if choice == "1":
            await run_live_trading()
        elif choice == "2":
            show_backtest_menu()
        elif choice == "3":
            show_stats()
        elif choice == "4":
            show_settings()
        elif choice == "5":
            console.print("[bold cyan]Thanks for playing! Good luck in the markets![/bold cyan]")
            sys.exit(0)

def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        console.print("\n[bold red]Game Over (Interrupted)[/bold red]")
        sys.exit(0)

if __name__ == "__main__":
    main()
