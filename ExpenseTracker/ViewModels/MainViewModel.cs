using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using ExpenseTracker.Models;
using ExpenseTracker.Data;
using System.Collections.ObjectModel;
using System.Windows;
using System.ComponentModel;
using ExpenseTracker.Views; // <-- for ExpenseFormWindow
using System.Windows.Input;

namespace ExpenseTracker.ViewModels
{
    public class MainViewModel : INotifyPropertyChanged
    {
        private ObservableCollection<Expense> _expenses = new();
        public ObservableCollection<Expense> Expenses
        {
            get => _expenses;
            set
            {
                _expenses = value;
                OnPropertyChanged(nameof(Expenses));
            }
        }

        private List<Expense> _allExpenses = new(); // holds all data for filtering

        private Expense? _selectedExpense;
        public Expense? SelectedExpense
        {
            get => _selectedExpense;
            set
            {
                _selectedExpense = value;
                OnPropertyChanged(nameof(SelectedExpense));
            }
        }

        private string _filterText = string.Empty;
        public string FilterText
        {
            get => _filterText;
            set
            {
                _filterText = value;
                OnPropertyChanged(nameof(FilterText));
                ApplyFilter(); // filter as user types
            }
        }

        // New: Currently opened expense for the popup
        private Expense _currentExpense;
        public Expense CurrentExpense
        {
            get => _currentExpense;
            set
            {
                _currentExpense = value;
                OnPropertyChanged(nameof(CurrentExpense));
            }
        }

        // Commands
        public RelayCommand OpenAddFormCommand { get; set; }
        public RelayCommand OpenEditFormCommand { get; set; }
        public RelayCommand DeleteCommand { get; set; }

        public MainViewModel()
        {
            OpenAddFormCommand = new RelayCommand(_ => OpenAddForm());
            OpenEditFormCommand = new RelayCommand(expense => OpenEditForm(expense as Expense));
            DeleteCommand = new RelayCommand(expense => DeleteExpense(expense as Expense));

            LoadData();
        }

        public void LoadData()
        {
            using (var context = new AppDbContext())
            {
                var data = context.Expenses.OrderBy(e => e.Id).ToList();

                // Assign display numbers
                int counter = 1;
                foreach (var exp in data)
                {
                    exp.DisplayNumber = counter++;
                }

                _allExpenses = data;
                ApplyFilter();
            }
        }

        private void ApplyFilter()
        {
            if (string.IsNullOrWhiteSpace(FilterText))
            {
                Expenses = new ObservableCollection<Expense>(_allExpenses);
            }
            else
            {
                var lower = FilterText.ToLower();
                var filtered = _allExpenses.Where(e =>
                    e.Description.ToLower().Contains(lower) ||
                    e.Amount.ToString().Contains(lower) ||
                    e.Date.ToString("d").Contains(lower)
                ).ToList();

                Expenses = new ObservableCollection<Expense>(filtered);
            }
        }

        public void OpenExpenseForm(Expense expense, bool isNew)
        {
            CurrentExpense = expense;

            var form = new ExpenseFormWindow { DataContext = this };
            var result = form.ShowDialog();

            if (result == true)
            {
                using (var context = new AppDbContext())
                {
                    if (isNew)
                    {
                        context.Expenses.Add(CurrentExpense);
                    }
                    else
                    {
                        var dbExpense = context.Expenses.Find(CurrentExpense.Id);
                        if (dbExpense != null)
                        {
                            dbExpense.Description = CurrentExpense.Description;
                            dbExpense.Amount = CurrentExpense.Amount;
                            dbExpense.Date = CurrentExpense.Date;
                        }
                    }
                    context.SaveChanges();
                }
                LoadData();
            }
        }

        public void OpenAddForm()
        {
            OpenExpenseForm(new Expense
            {
                Date = DateTime.Now
            }, true);
        }

        public void OpenEditForm(Expense expense)
        {
            if (expense == null) return;

            OpenExpenseForm(new Expense
            {
                Id = expense.Id,
                Description = expense.Description,
                Amount = expense.Amount,
                Date = expense.Date
            }, false);

        }


        private void DeleteExpense(Expense? expense)
        {
            if (expense == null) return;

            var result = MessageBox.Show("Are you sure you want to delete?", "Confirm Delete", MessageBoxButton.YesNo);
            if (result == MessageBoxResult.Yes)
            {
                using (var context = new AppDbContext())
                {
                    var dbExpense = context.Expenses.Find(expense.Id);
                    if (dbExpense != null)
                    {
                        context.Expenses.Remove(dbExpense);
                        context.SaveChanges();
                    }
                }
                LoadData();
            }
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged(string name)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }
    }
}
