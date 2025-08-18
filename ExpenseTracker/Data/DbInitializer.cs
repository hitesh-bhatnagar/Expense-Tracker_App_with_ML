using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using ExpenseTracker.Models;

namespace ExpenseTracker.Data
{
    public static class DbInitializer
    {
        public static void Initialize(AppDbContext context)
        {
            context.Database.EnsureCreated();

            if (context.Expenses.Any()) return;
            var expenses = new Expense[]
            {
                new Expense { Description = "Groceries", Amount = 1500, Date = DateTime.Now.AddDays(-10) },
                new Expense { Description = "Internet", Amount = 7550, Date = DateTime.Now.AddDays(-5) },
                new Expense { Description = "Transport", Amount = 5000, Date = DateTime.Now.AddDays(-2) }
            };

            context.Expenses.AddRange(expenses);
            context.SaveChanges();
        }
    }
}
