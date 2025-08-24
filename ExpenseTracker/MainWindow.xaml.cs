using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using CsvHelper;
using ExpenseTracker.Data;
using ExpenseTracker.Models;
using ExpenseTracker.ViewModels;
using Microsoft.Win32;

namespace ExpenseTracker
{
    public partial class MainWindow : Window
    {
        private bool _suppressHandler = false;

        public MainWindow()
        {
            InitializeComponent();
            DataContext = new MainViewModel();
        }

        // Export expenses to CSV
        private void ExportCsv_Click(object sender, RoutedEventArgs e)
        {
            var saveFileDialog = new SaveFileDialog
            {
                Filter = "CSV files (*.csv)|*.csv",
                FileName = "Expenses.csv"
            };

            if (saveFileDialog.ShowDialog() == true)
            {
                try
                {
                    using (var writer = new StreamWriter(saveFileDialog.FileName))
                    using (var csv = new CsvWriter(writer, CultureInfo.InvariantCulture))
                    {
                        csv.Context.RegisterClassMap<ExpenseMap>(); // Register the map
                        using var context = new AppDbContext();
                        var allExpenses = context.Expenses.ToList();
                        csv.WriteRecords(allExpenses);
                    }


                    MessageBox.Show("Expenses exported successfully!", "Export Complete", MessageBoxButton.OK, MessageBoxImage.Information);
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Error exporting data: " + ex.Message, "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        public void RunAnalyzer_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // 1. Export latest data from DB into CSV
                string projectRoot = Directory.GetParent(Directory.GetCurrentDirectory()).Parent.Parent.FullName;
                string mlFolder = Path.Combine(projectRoot, "ML");
                string csvPath = Path.Combine(mlFolder, "expenses.csv");
                string htmlPath = Path.Combine(mlFolder, "trend.html");

                using (var context = new AppDbContext())
                {
                    var expenses = context.Expenses.OrderBy(exp => exp.Date).ToList();
                    using (var writer = new StreamWriter(csvPath))
                    {
                        writer.WriteLine("Id,Description,Amount,Date");
                        foreach (var exp in expenses)
                        {
                            writer.WriteLine($"{exp.Id},\"{exp.Description}\",{exp.Amount},{exp.Date:yyyy-MM-dd}");
                        }
                    }
                }

                // 2. Run analyzer.py with venv Python
                string analyzerScript = "analyzer.py";
                string venvPython = Path.Combine(mlFolder, ".venv", "Scripts", "python.exe");

                var psi = new ProcessStartInfo
                {
                    FileName = venvPython,
                    Arguments = $"\"{analyzerScript}\" --out trend.html",
                    WorkingDirectory = mlFolder,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                string stdOutput, stdError;
                using (var process = Process.Start(psi))
                {
                    stdOutput = process.StandardOutput.ReadToEnd();
                    stdError = process.StandardError.ReadToEnd();
                    process.WaitForExit();
                }

                // Filter out harmless logs
                string filteredError = string.Join("\n",
                    stdError.Split('\n')
                            .Where(line => !line.Contains("INFO"))
                            .Where(line => !string.IsNullOrWhiteSpace(line))
                );

                if (!string.IsNullOrEmpty(filteredError))
                {
                    MessageBox.Show("Python error:\n" + filteredError, "Analyzer Error",
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                // 3. Open the latest HTML file in default browser
                if (File.Exists(htmlPath))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = htmlPath,   // ✅ plain file path (no file:///)
                        UseShellExecute = true
                    });
                }
                else
                {
                    MessageBox.Show("trend.html was not generated!", "Error",
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                MessageBox.Show("Analysis complete! Report opened in browser.", "Analyzer",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Error running analyzer: " + ex.Message, "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // Handle row edits to save changes to DB
        private void ExpenseGrid_RowEditEnding(object sender, DataGridRowEditEndingEventArgs e)
        {
            if (_suppressHandler)
                return;

            _suppressHandler = true;

            try
            {
                if (e.EditAction == DataGridEditAction.Commit)
                {
                    var grid = sender as DataGrid;

                    grid.CommitEdit(DataGridEditingUnit.Row, true);

                    if (e.Row.Item is Expense editedExpense)
                    {
                        using var context = new AppDbContext();

                        var existing = context.Expenses.Find(editedExpense.Id);

                        if (existing != null)
                        {
                            existing.Description = editedExpense.Description;
                            existing.Amount = editedExpense.Amount;

                            // Specify UTC kind for date
                            existing.Date = DateTime.SpecifyKind(editedExpense.Date, DateTimeKind.Utc);
                        }
                        else
                        {
                            context.Expenses.Add(editedExpense);
                        }

                        context.SaveChanges();

                        if (DataContext is MainViewModel vm)
                        {
                            vm.LoadData();
                        }
                    }
                }
            }
            finally
            {
                _suppressHandler = false;
            }
        }
    }
}
