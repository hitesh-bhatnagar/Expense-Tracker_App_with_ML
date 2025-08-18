using ExpenseTracker.Data;
using ExpenseTracker.ViewModels;

using ExpenseTracker.Models;
using System;
using System.Windows;

namespace ExpenseTracker.Views
{
    public partial class ExpenseFormWindow : Window
    {
        public ExpenseFormWindow()
        {
            InitializeComponent();
            Loaded += (s, e) =>
            {
                var fade = new System.Windows.Media.Animation.DoubleAnimation(0, 1, new Duration(TimeSpan.FromMilliseconds(200)));
                BeginAnimation(OpacityProperty, fade);
            };
        }

        public void Save_Click(object sender, RoutedEventArgs e)
        {
            var vm = DataContext as MainViewModel;
            if (vm?.CurrentExpense == null)
            {
                MessageBox.Show("Unexpected error: No expense data found.");
                return;
            }

            // Validation
            if (string.IsNullOrWhiteSpace(vm.CurrentExpense.Description))
            {
                MessageBox.Show("Description cannot be empty.", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            if (vm.CurrentExpense.Amount <= 0)
            {
                MessageBox.Show("Amount must be greater than zero.", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            if (vm.CurrentExpense.Date == default)
            {
                MessageBox.Show("Please select a valid date.", "Validation Error", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            // ✅ Only set DialogResult to true so MainViewModel handles saving
            DialogResult = true;
            Close();
        }



        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}
