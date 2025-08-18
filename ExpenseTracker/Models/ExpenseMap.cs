// this is so that when i import a csv file then it doesn't map the DisplayNumber

using CsvHelper.Configuration;
using ExpenseTracker.Models;

public class ExpenseMap : ClassMap<Expense>
{
    public ExpenseMap()
    {
        Map(e => e.Id);
        Map(e => e.Description);
        Map(e => e.Amount);
        Map(e => e.Date);
        
    }
}
